#!/usr/bin/env python3
"""Build a real-data paired-inference diagnostic from TuneTables fold results."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import statistics
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE_DIR = HERE / "cases/tunetables-top5"
ANALYZER_PATH = ROOT / "skills/paper-table/scripts/analyze_paired.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_analyzer():
    spec = importlib.util.spec_from_file_location("inferencebench_analyze_paired", ANALYZER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict, compact: bool = False) -> None:
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(value, indent=2, ensure_ascii=False)
    path.write_text(rendered + "\n")


def build_input(case: dict) -> dict:
    source_path = (CASE_DIR / case["source_case"]).resolve()
    source = json.loads(source_path.read_text())
    methods = [case["baseline"], *case["candidates"]]
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for record in source["records"]:
        if record["method"] in methods:
            grouped[(record["method"], record["dataset"])].append(float(record["accuracy"]))
    records = []
    for (method, dataset), values in grouped.items():
        if len(values) != 3:
            raise ValueError(f"expected three folds for {(method, dataset)!r}")
        records.append({"method": method, "dataset": dataset, "accuracy": statistics.fmean(values)})
    records.sort(key=lambda row: (row["dataset"], methods.index(row["method"])))
    if len(records) != len(methods) * case["paired_units"]:
        raise ValueError("unexpected paired dataset grid size")
    return {
        "schema_version": "paper-table-paired-inference-v1",
        "method_key": "method",
        "unit_key": "dataset",
        "score_key": "accuracy",
        "baseline": case["baseline"],
        "candidates": case["candidates"],
        "direction": "max",
        "records": records,
        "design": {
            "pairing": "complete",
            "unit_independence": "independent",
            "unit_description": case["independent_unit"],
            "unit_independence_evidence": "Each inferential unit is one distinct OpenML dataset; its three folds are averaged before comparison."
        },
        "test": {
            "name": "paired_sign_flip_mean",
            "alternative": "two-sided",
            "exchangeability": "paired_signs_exchangeable_under_null",
            "exchangeability_rationale": "Under the null of no systematic method difference across datasets, the orientation of each complete paired dataset difference is exchangeable.",
            "exact_max_pairs": 18,
            "monte_carlo_samples": 49999,
            "seed": 240211137
        },
        "confidence_interval": {
            "name": "paired_percentile_bootstrap_mean",
            "confidence_level": 0.95,
            "resamples": 5000,
            "seed": 20240808
        },
        "multiplicity": {
            "family_id": "tunetables-top5-current-snapshot",
            "correction": "holm",
            "alpha": 0.05
        },
        "provenance": {
            "source_case_id": "neurips24-tunetables-tabzilla",
            "source_revision": case["source_revision"],
            "paper_url": case["paper_url"],
            "snapshot_status": "version-drifted current author snapshot; not paper-time inference"
        }
    }


def table_spec(report: dict) -> dict:
    def rounded(value: float, precision: int) -> float:
        return float(f"{value:.{precision}f}")

    rows = []
    for result in report["results"]:
        rows.append({
            "method": result["method"],
            "improvement_pp": {
                "mean": rounded(100 * result["mean_improvement"], 2),
                "ci95": [rounded(100 * endpoint, 2) for endpoint in result["improvement_ci"]]
            },
            "p_raw": rounded(result["p_raw"], 5),
            "p_holm": rounded(result["p_adjusted"], 5),
            "significant": "Yes" if result["reject_null"] else "No"
        })
    return {
        "title": "Paired dataset-level comparison against TuneTables",
        "label": "tab:tunetables-paired-inference-current",
        "caption": "Candidate-minus-TuneTables accuracy differences on 98 paired datasets in the current author snapshot.",
        "columns": [
            {"key": "method", "label": "Candidate", "kind": "text"},
            {"key": "improvement_pp", "label": "Improvement [95% CI]", "kind": "metric", "direction": "max", "unit": "percentage points", "precision": 2},
            {"key": "p_raw", "label": "Raw p", "kind": "metric", "direction": "min", "unit": "probability", "precision": 5},
            {"key": "p_holm", "label": "Holm p", "kind": "metric", "direction": "min", "unit": "probability", "precision": 5},
            {"key": "significant", "label": "Reject at 0.05", "kind": "text"}
        ],
        "rows": rows,
        "emphasis": {"best": "none", "second": "none", "scope": "all"},
        "notes": [
            "Positive improvement favors the candidate; negative values favor TuneTables.",
            "Two-sided paired sign-flip tests use deterministic Monte Carlo; p-values are Holm-adjusted across four planned comparisons.",
            "Intervals are paired percentile-bootstrap intervals over datasets. This current snapshot is version-drifted and does not reproduce paper-time claims."
        ],
        "provenance": report["provenance"] | {"inference_report_schema": report["schema_version"]}
    }


def main() -> None:
    case = json.loads((CASE_DIR / "case.json").read_text())
    payload = build_input(case)
    report = load_analyzer().analyze(payload)
    table = table_spec(report)
    write_json(CASE_DIR / case["input"]["path"], payload, compact=True)
    write_json(CASE_DIR / case["expected_report"]["path"], report)
    write_json(CASE_DIR / case["table_spec"]["path"], table)
    print(json.dumps({
        "case": case["id"],
        "paired_units": report["design"]["n_units"],
        "comparisons": len(report["results"]),
        "rejections": sum(result["reject_null"] for result in report["results"])
    }, indent=2))


if __name__ == "__main__":
    main()
