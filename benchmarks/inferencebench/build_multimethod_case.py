#!/usr/bin/env python3
"""Build a real-data multi-method omnibus and gated post-hoc diagnostic."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE_DIR = HERE / "cases/tunetables-multimethod"
SOURCE_DIR = HERE / "cases/tunetables-top5"
ANALYZER_PATH = ROOT / "skills/paper-table/scripts/analyze_multimethod.py"


def load_analyzer():
    spec = importlib.util.spec_from_file_location("inferencebench_analyze_multimethod", ANALYZER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict, compact: bool = False) -> None:
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(value, indent=2, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n")


def build_input() -> dict:
    source = json.loads((SOURCE_DIR / "paired_input.json").read_text())
    methods = [source["baseline"], *source["candidates"]]
    return {
        "schema_version": "paper-table-multimethod-inference-v1",
        "method_key": source["method_key"],
        "block_key": source["unit_key"],
        "score_key": source["score_key"],
        "methods": methods,
        "direction": source["direction"],
        "records": source["records"],
        "design": {
            "blocks": "complete",
            "block_independence": "independent",
            "block_description": source["design"]["unit_description"],
            "block_independence_evidence": source["design"]["unit_independence_evidence"],
        },
        "omnibus": {
            "name": "friedman_block_permutation",
            "rank_tie_policy": "average",
            "exchangeability": "method_labels_exchangeable_within_blocks_under_global_null",
            "exchangeability_rationale": "Under the global null of identical method performance, the five method labels are exchangeable within each complete dataset block.",
            "alpha": 0.05,
            "exact_max_configurations": 100000,
            "monte_carlo_samples": 49999,
            "seed": 20240811,
        },
        "posthoc": {
            "baseline": source["baseline"],
            "candidates": source["candidates"],
            "baseline_selection_timing": "predeclared_before_outcome_inspection",
            "gatekeeping": "require_omnibus_rejection",
            "test": "paired_sign_flip_mean",
            "alternative": "two-sided",
            "exchangeability": source["test"]["exchangeability"],
            "exchangeability_rationale": source["test"]["exchangeability_rationale"],
            "exact_max_pairs": source["test"]["exact_max_pairs"],
            "monte_carlo_samples": source["test"]["monte_carlo_samples"],
            "seed": source["test"]["seed"],
            "confidence_interval": source["confidence_interval"],
            "multiplicity": source["multiplicity"],
        },
        "provenance": source["provenance"] | {
            "source_inference_case": "tunetables-top5-current-snapshot",
            "analysis_scope": "five-method omnibus followed by predeclared TuneTables-versus-all family",
        },
    }


def table_spec(report: dict) -> dict:
    posthoc = {row["method"]: row for row in report["posthoc"]["results"]}
    rows = []
    for descriptive in report["descriptive"]:
        method = descriptive["method"]
        result = posthoc.get(method)
        rows.append({
            "method": method,
            "mean_accuracy": round(100 * descriptive["mean_score"], 2),
            "average_rank": round(descriptive["average_rank"], 2),
            "improvement_pp": None if result is None else {
                "mean": round(100 * result["mean_improvement"], 2),
                "ci95": [round(100 * value, 2) for value in result["improvement_ci"]],
            },
            "p_holm": None if result is None else round(result["p_adjusted"], 5),
            "decision": "Reference" if result is None else ("Yes" if result["reject_null"] else "No"),
        })
    omnibus = report["omnibus"]
    return {
        "title": "Multi-method blocked comparison with a gated post-hoc family",
        "label": "tab:tunetables-multimethod-current",
        "caption": "Five-method comparison on 98 complete paired datasets in the current TuneTables author snapshot.",
        "columns": [
            {"key": "method", "label": "Method", "kind": "text"},
            {"key": "mean_accuracy", "label": "Mean accuracy", "kind": "metric", "direction": "max", "unit": "%", "precision": 2},
            {"key": "average_rank", "label": "Average rank", "kind": "metric", "direction": "min", "unit": "rank", "precision": 2},
            {"key": "improvement_pp", "label": "vs. TuneTables [95% CI]", "kind": "metric", "direction": "max", "unit": "percentage points", "precision": 2},
            {"key": "p_holm", "label": "Gated Holm p", "kind": "metric", "direction": "min", "unit": "probability", "precision": 5},
            {"key": "decision", "label": "Reject at 0.05", "kind": "text"},
        ],
        "rows": rows,
        "emphasis": {"best": "none", "second": "none", "scope": "all"},
        "notes": [
            f"Block-permutation Friedman omnibus: Q={omnibus['statistic']:.2f}, Monte Carlo p={omnibus['p_value']:.5f}; average rank 1 is best.",
            "Post-hoc p-values compare the predeclared TuneTables reference with every other method and are Holm-adjusted only after the omnibus gate.",
            f"Exact score ties receive average ranks ({omnibus['blocks_with_ties']} of {report['design']['n_blocks']} blocks contain ties).",
            "The current author snapshot is version-drifted and does not reproduce paper-time claims.",
        ],
        "provenance": report["provenance"] | {"inference_report_schema": report["schema_version"]},
    }


def main() -> None:
    payload = build_input()
    report = load_analyzer().analyze(payload)
    table = table_spec(report)
    write_json(CASE_DIR / "multimethod_input.json", payload, compact=True)
    write_json(CASE_DIR / "expected_report.json", report)
    write_json(CASE_DIR / "inference_table.json", table)
    print(json.dumps({
        "case": "tunetables-multimethod-current-snapshot",
        "blocks": report["design"]["n_blocks"],
        "methods": report["design"]["n_methods"],
        "omnibus_p": report["omnibus"]["p_value"],
        "omnibus_reject": report["omnibus"]["reject_global_null"],
        "posthoc_rejections": sum(row["reject_null"] for row in report["posthoc"]["results"]),
    }, indent=2))


if __name__ == "__main__":
    main()
