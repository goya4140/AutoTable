#!/usr/bin/env python3
"""Build the TuneTables cross-fold drift diagnostic from the pinned author snapshot."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE_DIR = HERE / "cases/neurips24-tunetables-tabzilla"
AGGREGATOR_PATH = HERE.parents[1] / "skills/paper-table/scripts/aggregate_crossfold.py"
COMPARATOR_PATH = HERE.parents[1] / "skills/paper-table/scripts/compare_snapshot.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_aggregator():
    spec = importlib.util.spec_from_file_location("statbench_aggregate_crossfold", AGGREGATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_comparator():
    spec = importlib.util.spec_from_file_location("statbench_compare_snapshot", COMPARATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def fold_number(dataset_fold_id: str) -> int:
    match = re.search(r"__fold_(\d+)$", dataset_fold_id)
    if not match:
        raise ValueError(f"cannot parse fold from {dataset_fold_id!r}")
    return int(match.group(1))


def build_payload(source_root: Path, case: dict) -> dict:
    files = {item["path"]: source_root / item["path"] for item in case["source"]["files"]}
    for item in case["source"]["files"]:
        if not files[item["path"]].is_file() or digest(files[item["path"]]) != item["sha256"]:
            raise ValueError(f"source hash mismatch: {item['path']}")
    targets = {row["dataset_name"] for row in read_csv(files["datasets_used/tabz_table1_datasets.csv"])}
    records = []
    baseline_path = files["05_2024_tabzilla_main_plotting_data/tt-rebuttal-all-algos-old-md-05_16_2024.csv"]
    for row in read_csv(baseline_path):
        if row["dataset_name"] in targets:
            records.append({
                "method": row["alg_name"],
                "dataset": row["dataset_name"],
                "fold": fold_number(row["dataset_fold_id"]),
                "accuracy": float(row["Accuracy__test"]),
            })
    excel_path = files["excelformer/excelformer-102124-dsnamedsid.csv"]
    trial_groups: dict[str, list[dict]] = defaultdict(list)
    for row in read_csv(excel_path):
        if row["dataset_name"] not in targets:
            continue
        fold = fold_number(row["dataset_fold_id"])
        if fold not in {0, 1, 2}:
            continue
        trial_groups[row["dataset_fold_id"]].append(row)
    tie_units = 0
    all_trials_tied_units = 0
    all_30_trials_tied_units = 0
    max_tied_trials = 0
    selected = []
    for rows in trial_groups.values():
        best_validation = max(float(row["Accuracy__val"]) for row in rows)
        tied = [row for row in rows if float(row["Accuracy__val"]) == best_validation]
        tie_units += len(tied) > 1
        all_trials_tied_units += len(tied) == len(rows)
        all_30_trials_tied_units += len(rows) == 30 and len(tied) == 30
        max_tied_trials = max(max_tied_trials, len(tied))
        selected.append(min(tied, key=lambda row: int(row["trial_number"])))
    for row in selected:
        records.append({
            "method": "ExcelFormer",
            "dataset": row["dataset_name"],
            "fold": fold_number(row["dataset_fold_id"]),
            "accuracy": float(row["Accuracy__test"]),
        })
    method_order = [row["method"] for row in json.loads((CASE_DIR / case["published_output"]).read_text())["rows"]]
    records.sort(key=lambda row: (row["dataset"], row["fold"], method_order.index(row["method"])))
    return {
        "schema_version": "paper-table-crossfold-v1",
        "title": "TuneTables TabZilla aggregate statistics from the current author snapshot",
        "label": "tab:tunetables-current-snapshot",
        "caption": "Aggregate classification results over 20 methods, 98 datasets, and three paired OpenML folds.",
        "method_key": "method",
        "method_label": "Model",
        "dataset_key": "dataset",
        "fold_key": "fold",
        "expected_folds": [0, 1, 2],
        "method_order": method_order,
        "score": {"key": "accuracy", "label": "Mean Acc.", "direction": "max", "unit": "proportion"},
        "precision": 3,
        "win_policy": "strict_unique_best",
        "records": records,
        "selection_audit": {
            "method": "ExcelFormer",
            "evaluation_units": len(trial_groups),
            "selection_metric": "Accuracy__val",
            "tie_break": "lowest trial_number",
            "test_metric_used_for_selection": False,
            "validation_tie_units": tie_units,
            "all_available_trials_tied_units": all_trials_tied_units,
            "all_30_trials_tied_units": all_30_trials_tied_units,
            "max_tied_trials": max_tied_trials
        },
        "emphasis": {"best": "bold", "second": "none", "scope": "all"},
        "provenance": {
            "paper_url": case["paper_url"],
            "source_repository": case["source"]["dataset_repository"],
            "source_revision": case["source"]["revision"],
            "snapshot_status": "post-publication author snapshot; exact paper-time snapshot unavailable",
        },
    }


def drift_report(case: dict, current: dict, published: dict) -> dict:
    generic = load_comparator().compare(current, published, "method")
    mismatches = [
        {
            "method": item["row"],
            "metric": item["metric"],
            "published": item["published"],
            "snapshot": item["snapshot"],
            "difference": item["difference"],
        }
        for item in generic["mismatches"]
    ]
    per_metric = {
        metric: {
            "exact_cells": values["exact_components"],
            "cells": values["components"],
            "mean_absolute_drift": values["mean_absolute_drift"],
            "max_absolute_drift": values["max_absolute_drift"],
        }
        for metric, values in generic["per_metric"].items()
    }
    return {
        "schema_version": "statbench-drift-report-v1",
        "case_id": case["id"],
        "status": generic["status"],
        "published_exact_gold": generic["published_exact_gold"],
        "exact_cells": generic["exact_components"],
        "cells": generic["components"],
        "exact_cell_rate": generic["exact_component_rate"],
        "mismatched_cells": len(mismatches),
        "structural_mismatches": generic["structural_mismatches"],
        "per_metric": per_metric,
        "mismatches": mismatches,
        "required_action": generic["required_action"],
    }


def write_json(path: Path, value: dict, compact: bool = False) -> None:
    if compact:
        path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    else:
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    case = json.loads((CASE_DIR / "case.json").read_text())
    published = json.loads((CASE_DIR / case["published_output"]).read_text())
    payload = build_payload(args.source_root, case)
    if len(payload["records"]) != case["selection"]["records"]:
        raise SystemExit(f"expected {case['selection']['records']} records, got {len(payload['records'])}")
    current = load_aggregator().aggregate(payload)
    report = drift_report(case, current, published)
    if report["published_exact_gold"]:
        raise SystemExit("expected the pinned post-publication snapshot to expose a version drift")
    write_json(CASE_DIR / case["raw_input"], payload, compact=True)
    write_json(CASE_DIR / case["current_expected"], current)
    write_json(CASE_DIR / case["drift_report"], report)
    print(json.dumps({
        "case": case["id"],
        "records": len(payload["records"]),
        "exact_cells": report["exact_cells"],
        "cells": report["cells"],
        "status": report["status"],
    }, indent=2))


if __name__ == "__main__":
    main()
