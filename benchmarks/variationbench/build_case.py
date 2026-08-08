#!/usr/bin/env python3
"""Build the controlled simulated-variation benchmark case."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE_DIR = HERE / "cases/assumption-only-controlled"
SIMULATOR_PATH = ROOT / "skills/paper-table/scripts/simulate_variation.py"


def load_simulator():
    spec = importlib.util.spec_from_file_location("variationbench_simulator", SIMULATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, value: dict, compact: bool = False) -> None:
    rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":")) if compact else json.dumps(value, indent=2, ensure_ascii=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered + "\n")


def build_input() -> dict:
    cells = []
    values = {
        ("Dataset-1", "Baseline"): (70.0, 3.0, "future_single_run", 1),
        ("Dataset-1", "Proposed"): (75.0, 4.0, "future_single_run", 1),
        ("Dataset-2", "Baseline"): (80.0, 5.0, "future_mean_of_independent_runs", 4),
        ("Dataset-2", "Proposed"): (82.0, 5.0, "future_mean_of_independent_runs", 4),
    }
    for (dataset, method), (anchor, sd, target, count) in values.items():
        cells.append({
            "identity": {"dataset": dataset, "method": method},
            "metric": "accuracy",
            "direction": "max",
            "unit": "%",
            "observed_value": anchor,
            "model": {
                "family": "truncated_normal",
                "scale_parameter": sd,
                "scale_parameterization": "parent_normal_sd_before_truncation",
                "scale_source": "author_assumption",
                "scale_source_detail": "Controlled benchmark assumption; no repeated-run evidence is claimed.",
                "lower_bound": 0.0,
                "upper_bound": 100.0,
                "future_target": target,
                "future_run_count": count,
            },
        })
    return {
        "schema_version": "paper-table-simulated-variation-v1",
        "scenario": {
            "label": "Assumption-only accuracy fluctuation illustration",
            "request_source": "author_requested",
            "purpose": "illustrative_possible_variation_only",
            "draws": 10_000,
            "seed": 20260808,
            "interval_mass": 0.9,
        },
        "cells": cells,
        "provenance": {
            "status": "synthetic_gold",
            "observed_anchor_source": "deterministic controlled benchmark",
            "assumption_source": "controlled author-assumption fixture",
        },
    }


def table_spec(report: dict) -> dict:
    rows = []
    for cell in report["cells"]:
        summary = cell["simulated_summary"]
        model = cell["simulation_model"]
        target = "Single future run" if model["future_run_count"] == 1 else f"Mean of {model['future_run_count']} future runs"
        rows.append({
            "cell": f"{cell['identity']['dataset']} · {cell['identity']['method']}",
            "observed_anchor": round(cell["observed_anchor"], 2),
            "assumed_scale": round(model["scale_parameter"], 2),
            "future_target": target,
            "simulated_lower": round(summary["lower"], 2),
            "simulated_upper": round(summary["upper"], 2),
            "status": "SIMULATED",
            "rank_eligible": False,
        })
    return {
        "title": "SIMULATED SCENARIO — possible accuracy fluctuation",
        "label": "tab:simulated-variation-scenario",
        "caption": "SIMULATED SCENARIO — assumption-only Monte Carlo illustration. Ranges are not observed uncertainty or confidence intervals.",
        "columns": [
            {"key": "cell", "label": "Dataset · method", "kind": "text"},
            {"key": "observed_anchor", "label": "Anchor", "kind": "text", "precision": 2},
            {"key": "assumed_scale", "label": "Assumed scale", "kind": "text", "precision": 2},
            {"key": "future_target", "label": "Future target", "kind": "text"},
            {"key": "simulated_lower", "label": "Sim. p05", "kind": "text", "precision": 2},
            {"key": "simulated_upper", "label": "Sim. p95", "kind": "text", "precision": 2},
            {"key": "status", "label": "Status", "kind": "text"},
        ],
        "rows": rows,
        "emphasis": {"best": "none", "second": "none", "scope": "all"},
        "notes": [
            f"Author-requested {report['scenario']['draws']:,}-draw scenario with seed {report['scenario']['seed']}; every scale is an explicit assumption.",
            "Anchor is the observed location point; Assumed scale is the parent-normal SD before truncation and is not observed uncertainty or the bounded distribution's realized SD.",
            "Do not use these ranges for significance, confidence claims, rankings, best/second emphasis, or verified results.",
            "Replace this scenario with real independent repeated runs when available; never blend simulated draws into observed aggregates.",
        ],
        "observed": False,
        "simulation_assumptions": [cell["simulation_model"] for cell in report["cells"]],
        "simulation_contract": report["global_contract"],
        "provenance": report["provenance"] | {"variation_report_schema": report["schema_version"]},
    }


def main() -> None:
    payload = build_input()
    report = load_simulator().simulate(payload)
    table = table_spec(report)
    write_json(CASE_DIR / "scenario_input.json", payload, compact=True)
    write_json(CASE_DIR / "expected_report.json", report)
    write_json(CASE_DIR / "scenario_table.json", table)
    descriptor = {
        "schema_version": "variationbench-case-v1",
        "id": "assumption-only-controlled",
        "status": "synthetic_gold",
        "cells": len(report["cells"]),
        "input": {"path": "scenario_input.json"},
        "expected_report": {"path": "expected_report.json"},
        "table_spec": {"path": "scenario_table.json"},
        "gold_properties": [
            "every range is explicitly simulated and author-requested",
            "observed anchors remain distinct from simulated draws",
            "cell streams are deterministic and order invariant",
            "assumed scale provenance, distribution, target, draw count, and seed are retained",
            "simulated cells are ineligible for verification, inference, ranking, and emphasis",
        ],
    }
    for key in ("input", "expected_report", "table_spec"):
        path = CASE_DIR / descriptor[key]["path"]
        descriptor[key]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(CASE_DIR / "case.json", descriptor)
    print(json.dumps({"case": descriptor["id"], "cells": len(report["cells"]), "draws_per_cell": report["scenario"]["draws"]}, indent=2))


if __name__ == "__main__":
    main()
