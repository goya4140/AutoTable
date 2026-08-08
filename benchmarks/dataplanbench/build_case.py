#!/usr/bin/env python3
"""Build a controlled data-acquisition planning benchmark."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MEAN_CASE_DIR = HERE / "cases/paired-precision-controlled"
DIFFERENCE_CASE_DIR = HERE / "cases/paired-difference-controlled"
MEAN_PLANNER_PATH = ROOT / "skills/paper-table/scripts/plan_more_data.py"
DIFFERENCE_PLANNER_PATH = ROOT / "skills/paper-table/scripts/plan_paired_difference.py"


def load_planner(path: Path = MEAN_PLANNER_PATH):
    spec = importlib.util.spec_from_file_location(f"dataplanbench_planner_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict, compact: bool = False) -> None:
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(value, indent=2, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n")


def build_input() -> dict:
    values = {
        ("Dataset-1", "Baseline"): [70.0, 72.0, 68.0, 71.0, 69.0],
        ("Dataset-1", "Method-A"): [73.0, 76.0, 72.0, 75.0],
        ("Dataset-1", "Method-B"): [74.0, 74.0, 74.0, 74.0, 74.0],
        ("Dataset-2", "Baseline"): [80.0, 81.0, 79.0],
        ("Dataset-2", "Method-A"): [83.0, 87.0, 81.0, 86.0, 82.0],
        ("Dataset-2", "Method-B"): [82.0, 84.0, 83.0, 85.0, None],
    }
    runs = []
    for (dataset, method), scores in values.items():
        for run_id, score in enumerate(scores):
            runs.append({"dataset": dataset, "method": method, "seed": run_id, "accuracy_pp": score})
    expected_groups = [
        {"dataset": dataset, "method": method}
        for dataset in ("Dataset-1", "Dataset-2")
        for method in ("Baseline", "Method-A", "Method-B")
    ]
    return {
        "schema_version": "paper-table-more-data-plan-v1",
        "group_keys": [{"key": "dataset"}, {"key": "method"}],
        "metrics": [{"key": "accuracy", "field": "accuracy_pp", "direction": "max", "unit": "percentage points"}],
        "runs": runs,
        "run_id_key": "seed",
        "repeat_unit": "independent training seed",
        "independence": "independent",
        "pairing": {
            "mode": "fixed_across_groups",
            "expected_groups": expected_groups,
            "expected_run_ids": [0, 1, 2, 3, 4],
        },
        "planning": {
            "estimand": "group_mean",
            "confidence_level": 0.95,
            "target_half_widths": {"accuracy": 1.5},
            "minimum_pilot_runs": 5,
            "maximum_total_runs": 30,
            "variance_assumption": "pilot_sd_stable_for_planning_only",
            "interval_assumption": "t_interval_appropriate_for_repeat_distribution",
        },
        "provenance": {
            "source": "deterministic controlled benchmark",
            "status": "synthetic_gold",
            "purpose": "test active requests for paired-run repair and precision-driven acquisition",
        },
    }


def build_paired_difference_input() -> dict:
    mean_input = build_input()
    return {
        "schema_version": "paper-table-paired-difference-plan-v1",
        "method_key": "method",
        "context_keys": ["dataset"],
        "metrics": mean_input["metrics"],
        "runs": mean_input["runs"],
        "run_id_key": "seed",
        "repeat_unit": mean_input["repeat_unit"],
        "independence": "independent",
        "pairing": {
            "mode": "baseline_vs_all_fixed_ids",
            "baseline": "Baseline",
            "candidates": ["Method-A", "Method-B"],
            "expected_contexts": [{"dataset": "Dataset-1"}, {"dataset": "Dataset-2"}],
            "expected_run_ids": [0, 1, 2, 3, 4],
        },
        "planning": {
            "estimand": "paired_mean_difference",
            "confidence_level": 0.95,
            "target_half_widths": {"accuracy": 1.5},
            "minimum_pilot_pairs": 5,
            "maximum_total_pairs": 30,
            "variance_assumption": "pilot_paired_difference_sd_stable_for_planning_only",
            "interval_assumption": "t_interval_appropriate_for_paired_difference_distribution",
        },
        "provenance": {
            "source": "deterministic controlled benchmark",
            "status": "synthetic_gold",
            "purpose": "test repair-first precision planning for paired baseline differences",
        },
    }
def table_spec(report: dict) -> dict:
    action_labels = {
        "target_met": "Target met",
        "additional_runs_provisionally_required": "Add runs",
        "collect_minimum_pilot_then_replan": "Pilot first",
        "zero_pilot_variance_requires_review": "Review zero SD",
        "target_not_reached_within_cap": "Review cap/target",
    }
    rows = []
    for cell in report["precision"]["cells"]:
        rows.append({
            "dataset": cell["group"]["dataset"],
            "method": cell["group"]["method"],
            "current_runs": cell["current_valid_runs"],
            "current_half_width": None if cell["current_ci_half_width"] is None else round(cell["current_ci_half_width"], 2),
            "target_half_width": round(cell["target_ci_half_width"], 2),
            "suggested_total": cell["required_total_runs"],
            "action": action_labels[cell["status"]],
        })
    repair_count = report["completeness"]["repair_count"]
    common = report["precision"]["request"]
    return {
        "title": "Active paired-run acquisition plan",
        "label": "tab:paired-run-acquisition-plan",
        "caption": "Observed-run audit and provisional 95% mean-precision plan for six method–dataset groups.",
        "columns": [
            {"key": "dataset", "label": "Dataset", "kind": "text"},
            {"key": "method", "label": "Method", "kind": "text"},
            {"key": "current_runs", "label": "Valid runs", "kind": "text", "precision": 0},
            {"key": "current_half_width", "label": "Current 95% CI ±", "kind": "text", "precision": 2},
            {"key": "target_half_width", "label": "Target ±", "kind": "text", "precision": 2},
            {"key": "suggested_total", "label": "Next checkpoint", "kind": "text", "precision": 0},
            {"key": "action", "label": "Action", "kind": "text"},
        ],
        "rows": rows,
        "emphasis": {"best": "none", "second": "none", "scope": "all"},
        "notes": [
            f"Repair {repair_count} missing or invalid existing run cells before adding new run IDs; then recompute this plan.",
            f"The current pilot provisionally suggests {common['additional_common_run_ids']} new paired run IDs across every group, up to {common['provisional_common_total_runs']} total runs.",
            "Suggested totals use the observed pilot SD in a Student-t mean interval; they are planning estimates, not guaranteed final widths.",
            "Zero pilot SD is sent for review rather than treated as proof that no more data are needed.",
        ],
        "provenance": report["provenance"] | {"data_plan_schema": report["schema_version"]},
    }


def paired_difference_table_spec(report: dict) -> dict:
    action_labels = {
        "target_met": "Target met",
        "additional_pairs_provisionally_required": "Add paired runs",
        "collect_minimum_pilot_then_replan": "Pilot first",
        "zero_pilot_difference_variance_requires_review": "Review zero pair SD",
        "target_not_reached_within_cap": "Review cap/target",
    }
    rows = []
    for cell in report["precision"]["cells"]:
        rows.append({
            "dataset": cell["context"]["dataset"],
            "candidate": cell["candidate"],
            "complete_pairs": cell["complete_pairs"],
            "mean_improvement": None if cell["mean_improvement"] is None else round(cell["mean_improvement"], 2),
            "paired_sd": None if cell["paired_difference_sd"] is None else round(cell["paired_difference_sd"], 2),
            "current_half_width": None if cell["current_ci_half_width"] is None else round(cell["current_ci_half_width"], 2),
            "target_half_width": round(cell["target_ci_half_width"], 2),
            "suggested_total": cell["required_total_pairs"],
            "action": action_labels[cell["status"]],
        })
    request = report["precision"]["request"]
    return {
        "title": "Paired-difference acquisition plan",
        "label": "tab:paired-difference-acquisition-plan",
        "caption": "Observed-pair audit and provisional 95% precision plan for baseline-relative mean improvements.",
        "columns": [
            {"key": "dataset", "label": "Dataset", "kind": "text"},
            {"key": "candidate", "label": "Candidate", "kind": "text"},
            {"key": "complete_pairs", "label": "Pairs", "kind": "text", "precision": 0},
            {"key": "mean_improvement", "label": "Mean improvement", "kind": "text", "precision": 2},
            {"key": "paired_sd", "label": "Pair SD", "kind": "text", "precision": 2},
            {"key": "current_half_width", "label": "Current 95% CI ±", "kind": "text", "precision": 2},
            {"key": "target_half_width", "label": "Target ±", "kind": "text", "precision": 2},
            {"key": "suggested_total", "label": "Next checkpoint", "kind": "text", "precision": 0},
            {"key": "action", "label": "Action", "kind": "text"},
        ],
        "rows": rows,
        "emphasis": {"best": "none", "second": "none", "scope": "all"},
        "notes": [
            f"Repair {report['completeness']['repair_count']} missing or invalid existing run cells before adding new IDs; then recompute this paired-difference plan.",
            f"The current pilot provisionally suggests {request['additional_common_run_ids']} new run IDs for the baseline and every candidate, up to {request['provisional_common_total_pairs']} complete pairs.",
            "Mean improvement is the within-run candidate minus baseline difference; positive values favor the candidate.",
            "Counts use paired-difference SD, not either method's marginal SD, and are planning estimates rather than guaranteed final widths.",
        ],
        "provenance": report["provenance"] | {"data_plan_schema": report["schema_version"]},
    }


def write_descriptor(case_dir: Path, case_id: str, properties: list[str]) -> None:
    import hashlib
    def sha(name: str) -> str:
        return hashlib.sha256((case_dir / name).read_bytes()).hexdigest()
    write_json(case_dir / "case.json", {
        "schema_version": "dataplanbench-case-v1",
        "id": case_id,
        "status": "synthetic_gold",
        "input": {"path": "planning_input.json", "sha256": sha("planning_input.json")},
        "expected_report": {"path": "expected_report.json", "sha256": sha("expected_report.json")},
        "table_spec": {"path": "acquisition_table.json", "sha256": sha("acquisition_table.json")},
        "gold_properties": properties,
    })


def main() -> None:
    payload = build_input()
    report = load_planner(MEAN_PLANNER_PATH).plan(payload)
    table = table_spec(report)
    write_json(MEAN_CASE_DIR / "planning_input.json", payload, compact=True)
    write_json(MEAN_CASE_DIR / "expected_report.json", report)
    write_json(MEAN_CASE_DIR / "acquisition_table.json", table)
    write_descriptor(MEAN_CASE_DIR, "paired-precision-controlled", [
        "missing existing paired runs are requested before new run IDs",
        "invalid metric cells receive explicit recovery requests",
        "group-mean precision counts use Student-t intervals and observed pilot SD",
        "zero pilot SD never claims a precision target is met",
    ])

    difference_payload = build_paired_difference_input()
    difference_report = load_planner(DIFFERENCE_PLANNER_PATH).plan(difference_payload)
    difference_table = paired_difference_table_spec(difference_report)
    write_json(DIFFERENCE_CASE_DIR / "planning_input.json", difference_payload, compact=True)
    write_json(DIFFERENCE_CASE_DIR / "expected_report.json", difference_report)
    write_json(DIFFERENCE_CASE_DIR / "acquisition_table.json", difference_table)
    write_descriptor(DIFFERENCE_CASE_DIR, "paired-difference-controlled", [
        "paired differences are aligned by declared run ID",
        "positive differences favor the candidate for either metric direction",
        "existing grid defects are repaired before new paired IDs",
        "precision counts use paired-difference SD rather than marginal group SD",
        "zero paired-difference SD remains unresolved",
    ])
    print(json.dumps({
        "cases": {
            "paired-precision-controlled": {
                "repairs": report["completeness"]["repair_count"],
                "precision_cells": len(report["precision"]["cells"]),
                "common_total": report["precision"]["request"]["provisional_common_total_runs"],
            },
            "paired-difference-controlled": {
                "repairs": difference_report["completeness"]["repair_count"],
                "precision_cells": len(difference_report["precision"]["cells"]),
                "common_total": difference_report["precision"]["request"]["provisional_common_total_pairs"],
            },
        },
    }, indent=2))


if __name__ == "__main__":
    main()
