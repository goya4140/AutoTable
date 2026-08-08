#!/usr/bin/env python3
"""Build a controlled unequal-cluster inference case with an estimand reversal."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE_DIR = HERE / "cases/clustered-controlled"
ANALYZER_PATH = ROOT / "skills/paper-table/scripts/analyze_paired.py"


def load_analyzer():
    spec = importlib.util.spec_from_file_location("inferencebench_analyze_clustered", ANALYZER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict, compact: bool = False) -> None:
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(value, indent=2, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n")


def build_input(estimand: str = "equal_cluster_mean") -> dict:
    records = []
    cluster_sizes = [2, 5, 2, 5, 2, 5, 2, 5]
    for study_index, size in enumerate(cluster_sizes, start=1):
        study = f"study-{study_index:02d}"
        volume_effect = -1.0 if size == 2 else 0.6
        for task_index in range(1, size + 1):
            task = f"{study}-task-{task_index:02d}"
            baseline = 70 + study_index * 0.5 + task_index * 0.1
            records.extend([
                {"method": "Baseline", "task": task, "study": study, "accuracy_pp": baseline},
                {"method": "Steady", "task": task, "study": study, "accuracy_pp": baseline + 1.0},
                {"method": "Volume-biased", "task": task, "study": study, "accuracy_pp": baseline + volume_effect},
            ])
    return {
        "schema_version": "paper-table-paired-inference-v2",
        "method_key": "method",
        "unit_key": "task",
        "score_key": "accuracy_pp",
        "baseline": "Baseline",
        "candidates": ["Steady", "Volume-biased"],
        "direction": "max",
        "records": records,
        "design": {
            "pairing": "complete",
            "unit_independence": "nested_within_independent_clusters",
            "unit_description": "evaluation tasks nested within independently sampled studies",
            "cluster_key": "study",
            "cluster_description": "independently sampled study",
            "cluster_independence": "independent",
            "cluster_independence_evidence": "The controlled design generates eight independent studies; tasks within a study share its study-level condition.",
            "cluster_estimand": estimand,
        },
        "test": {
            "name": "cluster_sign_flip_mean",
            "alternative": "two-sided",
            "exchangeability": "cluster_signs_exchangeable_under_null",
            "exchangeability_rationale": "Under the controlled null, each independent study-level aggregate difference is sign-exchangeable.",
            "exact_max_clusters": 18,
            "monte_carlo_samples": 9999,
            "seed": 20240809,
        },
        "confidence_interval": {
            "name": "cluster_percentile_bootstrap_mean",
            "confidence_level": 0.95,
            "resamples": 5000,
            "seed": 20240810,
        },
        "multiplicity": {
            "family_id": "clustered-controlled-two-method-family",
            "correction": "holm",
            "alpha": 0.05,
        },
        "provenance": {
            "source": "deterministic controlled benchmark",
            "status": "synthetic_gold",
            "purpose": "detect nested-unit randomization and silent cluster-weighting changes",
        },
    }


def table_spec(equal_report: dict, unit_report: dict) -> dict:
    unit_results = {row["method"]: row for row in unit_report["results"]}
    rows = []
    for result in equal_report["results"]:
        sensitivity = unit_results[result["method"]]
        rows.append({
            "method": result["method"],
            "equal_study_improvement": {
                "mean": round(result["mean_improvement"], 2),
                "ci95": [round(value, 2) for value in result["improvement_ci"]],
            },
            "unit_weighted_sensitivity": round(sensitivity["mean_improvement"], 2),
            "p_holm": round(result["p_adjusted"], 5),
            "significant": "Yes" if result["reject_null"] else "No",
        })
    return {
        "title": "Cluster-level inference with an explicit estimand sensitivity",
        "label": "tab:clustered-controlled-inference",
        "caption": "Candidate-minus-baseline accuracy differences across 28 tasks nested in eight independent studies.",
        "columns": [
            {"key": "method", "label": "Candidate", "kind": "text"},
            {"key": "equal_study_improvement", "label": "Equal-study improvement [95% CI]", "kind": "metric", "direction": "max", "unit": "percentage points", "precision": 2},
            {"key": "unit_weighted_sensitivity", "label": "Unit-weighted sensitivity", "kind": "metric", "direction": "max", "unit": "percentage points", "precision": 2},
            {"key": "p_holm", "label": "Primary Holm p", "kind": "metric", "direction": "min", "unit": "probability", "precision": 5},
            {"key": "significant", "label": "Reject at 0.05", "kind": "text"},
        ],
        "rows": rows,
        "emphasis": {"best": "none", "second": "none", "scope": "all"},
        "notes": [
            "Primary effects give each independent study equal weight; sign flips and bootstrap resampling operate on intact studies.",
            "The unit-weighted column is a labeled sensitivity analysis, not the estimand used for its neighboring p-value.",
            "Unequal cluster sizes make the Volume-biased effect reverse sign across the two declared estimands.",
        ],
        "provenance": equal_report["provenance"] | {
            "inference_report_schema": equal_report["schema_version"],
            "sensitivity_report_schema": unit_report["schema_version"],
        },
    }


def main() -> None:
    analyzer = load_analyzer()
    primary_input = build_input("equal_cluster_mean")
    sensitivity_input = build_input("unit_weighted_mean")
    primary_report = analyzer.analyze(primary_input)
    sensitivity_report = analyzer.analyze(sensitivity_input)
    table = table_spec(primary_report, sensitivity_report)
    write_json(CASE_DIR / "clustered_input.json", primary_input, compact=True)
    write_json(CASE_DIR / "expected_report.json", primary_report)
    write_json(CASE_DIR / "unit_weighted_report.json", sensitivity_report)
    write_json(CASE_DIR / "inference_table.json", table)
    print(json.dumps({
        "case": "clustered-controlled-estimand-reversal",
        "paired_units": primary_report["design"]["n_units"],
        "clusters": primary_report["design"]["n_clusters"],
        "comparisons": len(primary_report["results"]),
    }, indent=2))


if __name__ == "__main__":
    main()
