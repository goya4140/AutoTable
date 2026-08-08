#!/usr/bin/env python3
"""Aggregate a complete method × dataset × fold score grid into ranking statistics."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "paper-table-crossfold-v1"
OUTPUT_METRICS = (
    ("mean_score", "Mean score", "mean"),
    ("mean_rank", "Mean rank", "mean"),
    ("mean_z_score", "Mean Z-score", "mean"),
    ("std_z_score", "Std Z-score", "population_std"),
    ("median_z_score", "Median Z-score", "median"),
    ("num_wins", "Num. wins", "strict_unique_best_count"),
)


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _stable_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(values: list[Any]) -> str:
    encoded = json.dumps(sorted(values, key=_stable_key), ensure_ascii=False, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _rounded(value: float, precision: int) -> float | int:
    return int(round(value)) if precision == 0 else float(f"{value:.{precision}f}")


def _average_ranks(scores: dict[str, float], direction: str) -> dict[str, float]:
    ordered = sorted(scores.items(), key=lambda item: ((-item[1]) if direction == "max" else item[1], item[0]))
    ranks: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and ordered[end][1] == ordered[index][1]:
            end += 1
        average_rank = ((index + 1) + end) / 2
        for method, _ in ordered[index:end]:
            ranks[method] = average_rank
        index = end
    return ranks


def aggregate(payload: dict) -> dict:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    method_key = payload.get("method_key")
    dataset_key = payload.get("dataset_key")
    fold_key = payload.get("fold_key")
    score = payload.get("score", {})
    score_key = score.get("key")
    direction = score.get("direction")
    unit = score.get("unit")
    records = payload.get("records", [])
    expected_folds = payload.get("expected_folds", [])
    method_order = payload.get("method_order", [])
    win_policy = payload.get("win_policy", "strict_unique_best")
    if not all((method_key, dataset_key, fold_key, score_key, unit)):
        raise ValueError("method_key, dataset_key, fold_key, and score key/unit are required")
    if direction not in {"min", "max"}:
        raise ValueError("score.direction must be min or max")
    if win_policy != "strict_unique_best":
        raise ValueError("only win_policy='strict_unique_best' is supported")
    if not records or not expected_folds or len(expected_folds) != len({_stable_key(value) for value in expected_folds}):
        raise ValueError("records and a unique expected_folds list are required")

    units: dict[tuple[Any, Any], dict[str, float]] = defaultdict(dict)
    datasets_to_folds: dict[Any, set[str]] = defaultdict(set)
    observed_methods = set()
    for record in records:
        try:
            method = record[method_key]
            dataset = record[dataset_key]
            fold = record[fold_key]
            value = record[score_key]
        except KeyError as error:
            raise ValueError(f"record lacks required field {error.args[0]!r}") from error
        if not isinstance(method, str) or not method:
            raise ValueError("method identifiers must be non-empty strings")
        if not _finite(value):
            raise ValueError(f"score must be finite for method {method!r}")
        unit_key = (dataset, fold)
        if method in units[unit_key]:
            raise ValueError(f"duplicate method result for evaluation unit {unit_key!r}: {method!r}")
        units[unit_key][method] = float(value)
        datasets_to_folds[dataset].add(_stable_key(fold))
        observed_methods.add(method)

    if method_order:
        if len(method_order) != len(set(method_order)) or set(method_order) != observed_methods:
            raise ValueError("method_order must contain every observed method exactly once")
        methods = list(method_order)
    else:
        methods = sorted(observed_methods)
    expected_fold_keys = {_stable_key(value) for value in expected_folds}
    for dataset, folds in datasets_to_folds.items():
        if folds != expected_fold_keys:
            raise ValueError(f"dataset {dataset!r} does not contain the declared fold set")
    for unit_key, values in units.items():
        if set(values) != set(methods):
            missing = sorted(set(methods) - set(values))
            extra = sorted(set(values) - set(methods))
            raise ValueError(f"incomplete paired method grid at {unit_key!r}: missing={missing}, extra={extra}")

    collected = {method: {"score": [], "rank": [], "z": [], "wins": 0, "unit_ids": []} for method in methods}
    for (dataset, fold), values in sorted(units.items(), key=lambda item: _stable_key(item[0])):
        center = statistics.fmean(values.values())
        spread = statistics.pstdev(values.values())
        if spread == 0:
            raise ValueError(f"Z-score is undefined because all methods tie at {(dataset, fold)!r}")
        ranks = _average_ranks(values, direction)
        optimum = max(values.values()) if direction == "max" else min(values.values())
        winners = [method for method, value in values.items() if value == optimum]
        winner = winners[0] if len(winners) == 1 else None
        evaluation_id = {dataset_key: dataset, fold_key: fold}
        for method in methods:
            signed_z = (values[method] - center) / spread
            if direction == "min":
                signed_z = -signed_z
            collected[method]["score"].append(values[method])
            collected[method]["rank"].append(ranks[method])
            collected[method]["z"].append(signed_z)
            collected[method]["unit_ids"].append(evaluation_id)
            if method == winner:
                collected[method]["wins"] += 1

    precision = int(payload.get("precision", 3))
    if not 0 <= precision <= 12:
        raise ValueError("precision must be an integer from 0 to 12")
    rows = []
    audit = []
    for method in methods:
        values = collected[method]
        aggregates = {
            "mean_score": statistics.fmean(values["score"]),
            "mean_rank": statistics.fmean(values["rank"]),
            "mean_z_score": statistics.fmean(values["z"]),
            "std_z_score": statistics.pstdev(values["z"]),
            "median_z_score": statistics.median(values["z"]),
            "num_wins": values["wins"],
        }
        row = {method_key: method}
        for metric_key, _, operation in OUTPUT_METRICS:
            metric_precision = 0 if metric_key == "num_wins" else precision
            row[metric_key] = _rounded(aggregates[metric_key], metric_precision)
            audit.append({
                "group": {method_key: method},
                "metric": metric_key,
                "operation": operation,
                "n": len(values["unit_ids"]),
                "evaluation_unit_keys": [dataset_key, fold_key],
                "evaluation_units_sha256": _digest(values["unit_ids"]),
                "value_unrounded": aggregates[metric_key],
                "precision": metric_precision,
            })
        rows.append(row)

    metric_columns = []
    for metric_key, label, _ in OUTPUT_METRICS:
        metric_columns.append({
            "key": metric_key,
            "label": score.get("label", "Score") if metric_key == "mean_score" else label,
            "kind": "metric",
            "direction": "min" if metric_key in {"mean_rank", "std_z_score"} else "max",
            "unit": "count" if metric_key == "num_wins" else (unit if metric_key == "mean_score" else "dimensionless"),
            "precision": 0 if metric_key == "num_wins" else precision,
        })
    grid_ids = [{dataset_key: dataset, fold_key: fold} for dataset, fold in units]
    return {
        "title": payload.get("title", "Cross-fold method comparison"),
        "label": payload.get("label", "tab:crossfold-comparison"),
        "caption": payload.get("caption", "Statistics over a complete paired method-by-dataset-fold grid."),
        "columns": [{"key": method_key, "label": payload.get("method_label", "Method"), "kind": "text"}, *metric_columns],
        "rows": rows,
        "emphasis": payload.get("emphasis", {"best": "bold", "second": "none", "scope": "all"}),
        "notes": payload.get("notes", []) + [
            "Ranks use average ranks for ties; wins require a unique best method within an evaluation unit.",
            "Z-scores use the population standard deviation across methods within each dataset-fold; Std Z-score is the population standard deviation across evaluation units.",
            "The complete paired grid is required; missing method-fold results are rejected without imputation.",
        ],
        "provenance": {
            **payload.get("provenance", {}),
            "observed": True,
            "input_tier": "raw_runs",
            "aggregation_schema": SCHEMA_VERSION,
            "pairing_mode": "complete_method_by_dataset_fold_grid",
            "missing_run_policy": "error",
            "win_policy": win_policy,
        },
        "grid_audit": {
            "methods": len(methods),
            "datasets": len(datasets_to_folds),
            "folds_per_dataset": len(expected_folds),
            "evaluation_units": len(units),
            "records": len(records),
            "evaluation_units_sha256": _digest(grid_ids),
        },
        "aggregation_audit": audit,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = aggregate(json.loads(args.input.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    print(args.out)


if __name__ == "__main__":
    main()
