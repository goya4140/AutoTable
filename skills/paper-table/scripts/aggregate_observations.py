#!/usr/bin/env python3
"""Aggregate per-example observations into an auditable PaperTable spec."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


SUPPORTED_OPERATIONS = {"rate", "mean", "sum_over_count"}


def _finite(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _id_digest(values: list) -> str:
    encoded = json.dumps(sorted(values), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def aggregate(payload: dict) -> dict:
    if payload.get("schema_version") != "paper-table-observations-v1":
        raise ValueError("schema_version must be paper-table-observations-v1")
    group_keys = payload["group_keys"]
    observation_id_key = payload["observation_id_key"]
    denominators = payload["denominators"]
    metrics = payload["metrics"]
    observations = payload["observations"]
    if not group_keys or not metrics or not observations:
        raise ValueError("group_keys, metrics, and observations must be non-empty")

    denominator_sets = {}
    for name, ids in denominators.items():
        if not ids or len(ids) != len(set(ids)):
            raise ValueError(f"denominator {name!r} must contain unique observation IDs")
        denominator_sets[name] = set(ids)

    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for observation in observations:
        group = tuple(observation[key["key"]] for key in group_keys)
        grouped[group].append(observation)

    rows = []
    audit = []
    for group, items in grouped.items():
        by_id = {}
        for item in items:
            observation_id = item[observation_id_key]
            if observation_id in by_id:
                raise ValueError(f"duplicate observation ID {observation_id!r} in group {group!r}")
            by_id[observation_id] = item
        row = {key["key"]: value for key, value in zip(group_keys, group)}
        for metric in metrics:
            operation = metric["operation"]
            if operation not in SUPPORTED_OPERATIONS:
                raise ValueError(f"unsupported operation {operation!r}")
            denominator_name = metric["denominator"]
            if denominator_name not in denominator_sets:
                raise ValueError(f"unknown denominator {denominator_name!r}")
            ids = denominators[denominator_name]
            missing = denominator_sets[denominator_name] - set(by_id)
            if missing:
                raise ValueError(f"group {group!r} lacks denominator IDs for {metric['key']!r}: {sorted(missing)[:3]}")
            values = [by_id[observation_id].get(metric["field"]) for observation_id in ids]
            scale = float(metric.get("scale", 1.0))
            audit_item = {
                "group": {key["key"]: value for key, value in zip(group_keys, group)},
                "metric": metric["key"],
                "operation": operation,
                "denominator": denominator_name,
                "n": len(ids),
                "observation_id_key": observation_id_key,
                "observation_ids_sha256": _id_digest(ids),
            }
            if operation == "rate":
                if not all(isinstance(value, bool) for value in values):
                    raise ValueError(f"rate metric {metric['key']!r} requires boolean observations")
                numerator = sum(values)
                result = scale * numerator / len(values)
                audit_item["numerator_count"] = numerator
            elif operation == "mean":
                if not all(_finite(value) for value in values):
                    raise ValueError(f"mean metric {metric['key']!r} requires finite observations")
                result = scale * statistics.fmean(float(value) for value in values)
                audit_item["sum"] = math.fsum(float(value) for value in values)
            else:
                if not all(_finite(value) for value in values):
                    raise ValueError(f"sum_over_count metric {metric['key']!r} requires finite observations")
                total = math.fsum(float(value) for value in values)
                result = scale * total / len(values)
                audit_item["sum"] = total
            precision = int(metric.get("precision", 2))
            row[metric["key"]] = float(f"{result:.{precision}f}")
            audit_item.update({"scale": scale, "result_unrounded": result, "precision": precision})
            audit.append(audit_item)
        rows.append(row)

    columns = [{**key, "kind": "text"} for key in group_keys]
    for metric in metrics:
        columns.append({
            key: value
            for key, value in metric.items()
            if key not in {"field", "operation", "denominator", "scale"}
        } | {"kind": "metric"})
    return {
        "title": payload.get("title", "Aggregated observations"),
        "label": payload.get("label", "tab:aggregated-observations"),
        "caption": payload.get("caption", "Results aggregated from per-example observations."),
        "columns": columns,
        "rows": rows,
        "emphasis": payload.get("emphasis", {"best": "bold", "second": "none", "scope": "all"}),
        "notes": payload.get("notes", []),
        "provenance": {
            **payload.get("provenance", {}),
            "observed": True,
            "input_tier": "raw_runs",
            "unit_of_observation": payload.get("unit_of_observation", "example"),
        },
        "aggregation_audit": audit,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("observations", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(json.loads(args.observations.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
