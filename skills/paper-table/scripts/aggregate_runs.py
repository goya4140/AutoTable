#!/usr/bin/env python3
"""Aggregate genuinely independent repeated runs into an auditable table spec."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-table-runs-v1"
SUPPORTED_UNCERTAINTY = {"none", "sd", "se"}
SUPPORTED_PAIRING = {"fixed_across_groups", "group_specific"}


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _id_digest(values: list[Any]) -> str:
    encoded = json.dumps(sorted(values, key=_stable_key), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _rounded(value: float, precision: int) -> float:
    return float(f"{value:.{precision}f}")


def aggregate(payload: dict) -> dict:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    group_keys = payload.get("group_keys", [])
    metrics = payload.get("metrics", [])
    runs = payload.get("runs", [])
    run_id_key = payload.get("run_id_key")
    repeat_unit = payload.get("repeat_unit")
    independence = payload.get("independence")
    reported_uncertainty = payload.get("reported_uncertainty", "none")
    pairing = payload.get("pairing", {})
    pairing_mode = pairing.get("mode", "fixed_across_groups")
    missing_policy = pairing.get("missing_policy", "error")

    if not group_keys or not metrics or not runs:
        raise ValueError("group_keys, metrics, and runs must be non-empty")
    if not run_id_key or not repeat_unit:
        raise ValueError("run_id_key and repeat_unit are required")
    if independence != "independent":
        raise ValueError("independence must be explicitly declared as independent")
    if reported_uncertainty not in SUPPORTED_UNCERTAINTY:
        raise ValueError(f"reported_uncertainty must be one of {sorted(SUPPORTED_UNCERTAINTY)}")
    if pairing_mode not in SUPPORTED_PAIRING:
        raise ValueError(f"pairing.mode must be one of {sorted(SUPPORTED_PAIRING)}")
    if missing_policy != "error":
        raise ValueError("only pairing.missing_policy='error' is supported; imputation is forbidden")

    group_names = [item["key"] for item in group_keys]
    metric_names = [item["key"] for item in metrics]
    if len(group_names) != len(set(group_names)) or len(metric_names) != len(set(metric_names)):
        raise ValueError("group and metric keys must be unique")
    for metric in metrics:
        if metric.get("direction") not in {"min", "max"} or "unit" not in metric:
            raise ValueError(f"metric {metric.get('key')!r} requires direction and unit")
        precision = metric.get("precision", 2)
        if not isinstance(precision, int) or not 0 <= precision <= 12:
            raise ValueError(f"metric {metric['key']!r} precision must be an integer from 0 to 12")

    grouped: dict[tuple[Any, ...], list[dict]] = defaultdict(list)
    for run in runs:
        try:
            group = tuple(run[name] for name in group_names)
            run[run_id_key]
        except KeyError as error:
            raise ValueError(f"run lacks required field {error.args[0]!r}") from error
        grouped[group].append(run)

    expected_ids: list[Any] | None = None
    rows = []
    audit = []
    for group in sorted(grouped, key=_stable_key):
        items = grouped[group]
        run_ids = [item[run_id_key] for item in items]
        if len(run_ids) != len({_stable_key(value) for value in run_ids}):
            raise ValueError(f"duplicate run id in group {group!r}")
        if len(items) < 2:
            raise ValueError(f"at least two independent runs required for group {group!r}")
        run_ids = sorted(run_ids, key=_stable_key)
        by_id = {_stable_key(item[run_id_key]): item for item in items}
        if pairing_mode == "fixed_across_groups":
            if expected_ids is None:
                expected_ids = run_ids
            elif [_stable_key(value) for value in run_ids] != [_stable_key(value) for value in expected_ids]:
                raise ValueError(f"group {group!r} violates fixed_across_groups run pairing")

        group_map = dict(zip(group_names, group))
        row = dict(group_map)
        for metric in metrics:
            field = metric.get("field", metric["key"])
            ordered_items = [by_id[_stable_key(run_id)] for run_id in run_ids]
            values = [item.get(field) for item in ordered_items]
            if not all(_finite(value) for value in values):
                raise ValueError(f"metric {metric['key']!r} requires a finite value for every run in group {group!r}")
            values = [float(value) for value in values]
            mean = statistics.fmean(values)
            sample_sd = statistics.stdev(values)
            se = sample_sd / math.sqrt(len(values))
            precision = metric.get("precision", 2)
            if reported_uncertainty == "none":
                cell: Any = _rounded(mean, precision)
                reported_value = None
            else:
                spread = sample_sd if reported_uncertainty == "sd" else se
                cell = {"mean": _rounded(mean, precision), reported_uncertainty: _rounded(spread, precision)}
                reported_value = spread
            row[metric["key"]] = cell
            audit.append({
                "group": group_map,
                "metric": metric["key"],
                "operation": "mean",
                "n": len(values),
                "repeat_unit": repeat_unit,
                "independence": independence,
                "run_id_key": run_id_key,
                "run_ids": run_ids,
                "run_ids_sha256": _id_digest(run_ids),
                "sum": math.fsum(values),
                "mean_unrounded": mean,
                "sample_sd": sample_sd,
                "se": se,
                "reported_uncertainty": reported_uncertainty,
                "reported_value_unrounded": reported_value,
                "precision": precision,
            })
        rows.append(row)

    columns = [{**item, "kind": "text"} for item in group_keys]
    columns.extend({key: value for key, value in metric.items() if key != "field"} | {"kind": "metric"} for metric in metrics)
    uncertainty_note = (
        "Only means are displayed; sample SD and SE remain in the aggregation audit."
        if reported_uncertainty == "none"
        else f"Displayed uncertainty is {reported_uncertainty}, computed across independent {repeat_unit} units."
    )
    return {
        "title": payload.get("title", "Aggregated repeated runs"),
        "label": payload.get("label", "tab:aggregated-runs"),
        "caption": payload.get("caption", f"Mean over independent {repeat_unit} units."),
        "columns": columns,
        "rows": rows,
        "emphasis": payload.get("emphasis", {"best": "bold", "second": "none", "scope": "all"}),
        "notes": payload.get("notes", []) + [uncertainty_note, "Missing runs are rejected; no imputation is performed."],
        "provenance": {
            **payload.get("provenance", {}),
            "observed": True,
            "input_tier": "raw_runs",
            "unit_of_observation": repeat_unit,
            "independence": independence,
            "pairing_mode": pairing_mode,
            "missing_run_policy": missing_policy,
            "reported_uncertainty": reported_uncertainty,
        },
        "aggregation_audit": audit,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runs", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(json.loads(args.runs.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
