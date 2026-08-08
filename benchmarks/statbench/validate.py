#!/usr/bin/env python3
"""Validate all checked-in StatBench cases from source artifact to paper cell."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_diamond(case_dir: Path) -> list[str]:
    errors = []
    case = json.loads((case_dir / "case.json").read_text())
    source_path = case_dir / case["source"]["local_path"]
    if digest(source_path) != case["source"]["sha256"]:
        return ["author source hash mismatch"]
    builder = load(HERE / "build_diamond_case.py", "statbench_diamond_builder")
    aggregator = builder.load_aggregator()
    source = json.loads(source_path.read_text())
    payload = json.loads((case_dir / case["derived_input"]).read_text())
    expected = json.loads((case_dir / case["expected_output"]).read_text())
    if payload != builder.build_payload(source, case):
        errors.append("raw_runs.json is not reproducible from the author source")
    recomputed = aggregator.aggregate(payload)
    if recomputed != expected:
        errors.append("expected.json is not reproducible from raw_runs.json")
    cells = {row["game"]: row["return"] for row in recomputed["rows"]}
    if cells != case["published_cells"]:
        errors.append("recomputed cells differ from the published table")
    if len(payload.get("runs", [])) != 130 or len(recomputed.get("aggregation_audit", [])) != 26:
        errors.append("expected 130 raw runs and 26 cell-level audits")
    if any(item.get("n") != 5 or item.get("run_ids") != [0, 1, 2, 3, 4] for item in recomputed.get("aggregation_audit", [])):
        errors.append("each cell must preserve the fixed five-seed audit")
    if case.get("published_exact_gold") is not True or case.get("status") != "exact_published_reconstruction":
        errors.append("DIAMOND must remain explicitly admitted as exact published gold")
    return errors


def validate_tunetables(case_dir: Path) -> list[str]:
    errors = []
    case = json.loads((case_dir / "case.json").read_text())
    for artifact in case.get("derived_artifacts", []):
        path = case_dir / artifact["path"]
        if not path.is_file() or digest(path) != artifact["sha256"]:
            errors.append(f"derived artifact hash mismatch: {artifact['path']}")
    if errors:
        return errors
    builder = load(HERE / "build_tunetables_case.py", "statbench_tunetables_builder")
    payload = json.loads((case_dir / case["raw_input"]).read_text())
    current = json.loads((case_dir / case["current_expected"]).read_text())
    published = json.loads((case_dir / case["published_output"]).read_text())
    report = json.loads((case_dir / case["drift_report"]).read_text())
    recomputed = builder.load_aggregator().aggregate(payload)
    if recomputed != current:
        errors.append("current_expected.json is not reproducible from raw_fold_scores.json")
    recomputed_report = builder.drift_report(case, recomputed, published)
    if recomputed_report != report:
        errors.append("drift_report.json is not reproducible from current and published cells")
    grid = recomputed.get("grid_audit", {})
    expected_grid = {"methods": 20, "datasets": 98, "folds_per_dataset": 3, "evaluation_units": 294, "records": 5880}
    for key, expected in expected_grid.items():
        if grid.get(key) != expected:
            errors.append(f"grid audit {key} must equal {expected}")
    selection = payload.get("selection_audit", {})
    expected_selection = {
        "evaluation_units": 294,
        "selection_metric": "Accuracy__val",
        "tie_break": "lowest trial_number",
        "test_metric_used_for_selection": False,
        "validation_tie_units": case["selection"]["excelformer_validation_tie_units"],
        "all_available_trials_tied_units": case["selection"]["excelformer_all_available_trials_tied_units"],
        "all_30_trials_tied_units": case["selection"]["excelformer_all_30_trials_tied_units"],
        "max_tied_trials": case["selection"]["excelformer_max_tied_trials"],
    }
    for key, expected in expected_selection.items():
        if selection.get(key) != expected:
            errors.append(f"selection audit {key} must equal {expected!r}")
    if case.get("published_exact_gold") is not False or report.get("published_exact_gold") is not False:
        errors.append("a drift diagnostic must not be admitted as exact published gold")
    if report.get("status") != "source_snapshot_drift_detected" or report.get("exact_cells") != 20 or report.get("cells") != 120:
        errors.append("unexpected pinned-snapshot drift signature")
    return errors


def main() -> None:
    failures = {}
    exact_gold_cases = 0
    drift_diagnostics = 0
    for case_dir in sorted((HERE / "cases").iterdir()):
        if not case_dir.is_dir():
            continue
        case = json.loads((case_dir / "case.json").read_text())
        exact_gold_cases += case.get("published_exact_gold") is True
        drift_diagnostics += case.get("status") == "source_snapshot_drift_diagnostic"
        if case["id"] == "neurips24-diamond-atari":
            errors = validate_diamond(case_dir)
        elif case["id"] == "neurips24-tunetables-tabzilla":
            errors = validate_tunetables(case_dir)
        else:
            errors = ["no validator registered"]
        if errors:
            failures[case["id"]] = errors
    report = {
        "passed": not failures,
        "cases": len(list((HERE / "cases").glob("*/case.json"))),
        "exact_gold_cases": exact_gold_cases,
        "drift_diagnostics": drift_diagnostics,
        "failures": failures,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
