#!/usr/bin/env python3
"""Build deterministic semantic perturbations for PaperTable-Controlled."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "controlled" / "cases.jsonl"


def first_metric(spec: dict) -> dict:
    return next(column for column in spec["columns"] if column.get("kind") == "metric")


def first_metric_cell(spec: dict) -> tuple[dict, str]:
    keys = [column["key"] for column in spec["columns"] if column.get("kind") == "metric"]
    for row in spec["rows"]:
        for key in keys:
            if row.get(key) is not None:
                return row, key
    raise ValueError("no metric cell")


def first_uncertain_cell(spec: dict) -> tuple[dict, str, str]:
    keys = [column["key"] for column in spec["columns"] if column.get("kind") == "metric"]
    for row in spec["rows"]:
        for key in keys:
            cell = row.get(key)
            if isinstance(cell, dict):
                for uncertainty in ("sd", "se", "ci90", "ci95"):
                    if uncertainty in cell:
                        return row, key, uncertainty
    raise ValueError("no uncertain cell")


def apply_mutation(spec: dict, mutation: str) -> dict:
    candidate = copy.deepcopy(spec)
    if mutation == "numeric_value":
        row, key = first_metric_cell(candidate)
        cell = row[key]
        if isinstance(cell, dict):
            cell["mean"] = -cell["mean"] if cell["mean"] != 0 else 1.0
        else:
            row[key] = -cell if cell != 0 else 1.0
    elif mutation == "metric_direction":
        column = first_metric(candidate)
        column["direction"] = "min" if column.get("direction") == "max" else "max"
    elif mutation == "metric_unit":
        column = first_metric(candidate)
        column["unit"] = "incorrect-unit"
    elif mutation == "uncertainty_kind":
        row, key, uncertainty = first_uncertain_cell(candidate)
        replacement = "se" if uncertainty != "se" else "sd"
        row[key][replacement] = row[key].pop(uncertainty)
    elif mutation == "comparison_eligibility":
        row = candidate["rows"][-1]
        row["rank_eligible"] = not row.get("rank_eligible", True)
    elif mutation == "emphasis_policy":
        candidate.setdefault("emphasis", {})["scope"] = "group" if candidate.get("emphasis", {}).get("scope") != "group" else "all"
    elif mutation == "row_omission":
        candidate["rows"].pop(0)
    else:
        raise ValueError(f"unknown mutation: {mutation}")
    return candidate


def build() -> list[dict[str, Any]]:
    cases = []
    for case_path in sorted((HERE / "cases").glob("*/case.json")):
        case = json.loads(case_path.read_text())
        spec = json.loads((case_path.parent / "x.json").read_text())
        mutations = [
            ("numeric_value", "numeric_fidelity"),
            ("metric_direction", "metric_semantics"),
            ("metric_unit", "metric_semantics"),
            ("comparison_eligibility", "comparison_validity"),
            ("emphasis_policy", "comparison_validity"),
            ("row_omission", "structural_fidelity"),
        ]
        try:
            first_uncertain_cell(spec)
            mutations.append(("uncertainty_kind", "uncertainty_semantics"))
        except ValueError:
            pass
        for mutation, expected in mutations:
            cases.append({
                "id": f"{case['id']}--{mutation}",
                "base_case_id": case["id"],
                "mutation": mutation,
                "expected_violation_category": expected,
            })
    return cases


def main() -> None:
    cases = build()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("".join(json.dumps(case, ensure_ascii=False) + "\n" for case in cases))
    print(f"wrote {len(cases)} controlled cases to {OUTPUT}")


if __name__ == "__main__":
    main()
