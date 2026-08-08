#!/usr/bin/env python3
"""Evaluate a candidate table spec against a PaperBench semantic contract."""
from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

SCIENTIFIC_CATEGORIES = {
    "numeric_fidelity",
    "metric_semantics",
    "uncertainty_semantics",
    "comparison_validity",
    "provenance",
}
UNCERTAINTY_KEYS = ("sd", "se", "ci90", "ci95")


def violation(category: str, path: str, message: str, expected: Any = None, actual: Any = None) -> dict:
    item = {"category": category, "path": path, "message": message}
    if expected is not None:
        item["expected"] = expected
    if actual is not None:
        item["actual"] = actual
    return item


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def compare_number(expected: Any, actual: Any) -> bool:
    return finite_number(expected) and finite_number(actual) and math.isclose(
        float(expected), float(actual), rel_tol=1e-12, abs_tol=1e-12
    )


def uncertainty_kind(cell: Any) -> str | None:
    if not isinstance(cell, dict):
        return None
    present = [key for key in UNCERTAINTY_KEYS if key in cell]
    return present[0] if len(present) == 1 else "+".join(present) if present else None


def compare_cell(expected: Any, actual: Any, path: str) -> list[dict]:
    errors = []
    if isinstance(expected, dict) and "mean" in expected:
        if not isinstance(actual, dict) or "mean" not in actual:
            return [violation("uncertainty_semantics", path, "structured metric cell was flattened", expected, actual)]
        if not compare_number(expected["mean"], actual["mean"]):
            errors.append(violation("numeric_fidelity", f"{path}.mean", "mean changed", expected["mean"], actual["mean"]))
        expected_kind = uncertainty_kind(expected)
        actual_kind = uncertainty_kind(actual)
        if expected_kind != actual_kind:
            errors.append(violation("uncertainty_semantics", path, "uncertainty kind changed", expected_kind, actual_kind))
        if expected_kind and expected_kind in expected and expected_kind in actual:
            expected_value = expected[expected_kind]
            actual_value = actual[expected_kind]
            if isinstance(expected_value, list):
                if not isinstance(actual_value, list) or len(expected_value) != len(actual_value) or any(
                    not compare_number(left, right) for left, right in zip(expected_value, actual_value)
                ):
                    errors.append(violation("numeric_fidelity", f"{path}.{expected_kind}", "interval changed", expected_value, actual_value))
            elif not compare_number(expected_value, actual_value):
                errors.append(violation("numeric_fidelity", f"{path}.{expected_kind}", "uncertainty value changed", expected_value, actual_value))
        return errors
    if finite_number(expected):
        if not compare_number(expected, actual):
            errors.append(violation("numeric_fidelity", path, "numeric value changed", expected, actual))
    elif expected != actual:
        errors.append(violation("structural_fidelity", path, "cell content changed", expected, actual))
    return errors


def column_map(spec: dict) -> dict[str, dict]:
    return {column.get("key"): column for column in spec.get("columns", []) if isinstance(column, dict) and column.get("key")}


def row_map(spec: dict, row_key: str) -> tuple[dict[Any, dict], list[Any]]:
    rows = {}
    duplicates = []
    for row in spec.get("rows", []):
        identity = row.get(row_key)
        if identity in rows:
            duplicates.append(identity)
        rows[identity] = row
    return rows, duplicates


def evaluate(reference: dict, candidate: dict, case: dict) -> dict:
    contract = case["semantic_contract"]
    row_key = contract["row_identity_key"]
    errors: list[dict] = []

    reference_columns = column_map(reference)
    candidate_columns = column_map(candidate)
    for key in reference_columns.keys() - candidate_columns.keys():
        errors.append(violation("structural_fidelity", f"columns.{key}", "required column missing"))
    for key in candidate_columns.keys() - reference_columns.keys():
        errors.append(violation("structural_fidelity", f"columns.{key}", "unexpected column added"))
    for key in reference_columns.keys() & candidate_columns.keys():
        expected_column = reference_columns[key]
        actual_column = candidate_columns[key]
        if expected_column.get("label") != actual_column.get("label"):
            errors.append(violation("structural_fidelity", f"columns.{key}.label", "column label changed", expected_column.get("label"), actual_column.get("label")))
        if expected_column.get("kind") == "metric":
            for field in ("direction", "unit"):
                if expected_column.get(field) != actual_column.get(field):
                    errors.append(violation("metric_semantics", f"columns.{key}.{field}", f"metric {field} changed", expected_column.get(field), actual_column.get(field)))

    panels = candidate.get("layout", {}).get("panels")
    if panels is not None:
        metric_order = [column["key"] for column in candidate.get("columns", []) if column.get("kind") == "metric"]
        if not isinstance(panels, list) or len(panels) < 2:
            errors.append(violation("structural_fidelity", "layout.panels", "panel layout requires at least two panels"))
        else:
            valid_panels = [panel for panel in panels if isinstance(panel, dict) and isinstance(panel.get("metric_keys"), list)]
            if len(valid_panels) != len(panels):
                errors.append(violation("structural_fidelity", "layout.panels", "every panel requires a metric_keys array"))
            covered = [key for panel in valid_panels for key in panel["metric_keys"]]
            if covered != metric_order or len(covered) != len(set(covered)):
                errors.append(violation("structural_fidelity", "layout.panels", "panels must cover every metric exactly once in original order", metric_order, covered))
            for index, panel in enumerate(valid_panels):
                groups = {candidate_columns.get(key, {}).get("group") for key in panel["metric_keys"]}
                groups.discard(None)
                if len(groups) > 1:
                    errors.append(violation("comparison_validity", f"layout.panels.{index}", "one panel mixes distinct metric groups", actual=sorted(groups)))

    reference_rows, reference_duplicates = row_map(reference, row_key)
    candidate_rows, candidate_duplicates = row_map(candidate, row_key)
    for identity in reference_duplicates:
        errors.append(violation("provenance", f"rows.{identity}", "reference row identity is not unique"))
    for identity in candidate_duplicates:
        errors.append(violation("provenance", f"rows.{identity}", "candidate row identity is not unique"))
    for identity in reference_rows.keys() - candidate_rows.keys():
        errors.append(violation("structural_fidelity", f"rows.{identity}", "required row missing"))
    for identity in candidate_rows.keys() - reference_rows.keys():
        errors.append(violation("structural_fidelity", f"rows.{identity}", "unexpected row added"))

    for identity in reference_rows.keys() & candidate_rows.keys():
        expected_row = reference_rows[identity]
        actual_row = candidate_rows[identity]
        if expected_row.get("group") != actual_row.get("group"):
            errors.append(violation("comparison_validity", f"rows.{identity}.group", "comparison group changed", expected_row.get("group"), actual_row.get("group")))
        if expected_row.get("rank_eligible", True) != actual_row.get("rank_eligible", True):
            errors.append(violation("comparison_validity", f"rows.{identity}.rank_eligible", "ranking eligibility changed", expected_row.get("rank_eligible", True), actual_row.get("rank_eligible", True)))
        for key, column in reference_columns.items():
            if column.get("kind") != "metric":
                continue
            errors.extend(compare_cell(expected_row.get(key), actual_row.get(key), f"rows.{identity}.{key}"))

    if reference.get("emphasis", {}) != candidate.get("emphasis", {}):
        errors.append(violation("comparison_validity", "emphasis", "emphasis policy changed", reference.get("emphasis", {}), candidate.get("emphasis", {})))

    for group in contract["comparison_groups"]:
        allowed = set(group["row_values"])
        excluded = set(group.get("excluded_row_values", []))
        overlap = allowed & excluded
        if overlap:
            errors.append(violation("provenance", f"semantic_contract.comparison_groups.{group['id']}", "rows cannot be both comparable and excluded", actual=sorted(overlap)))
        missing = (allowed | excluded) - reference_rows.keys()
        if missing:
            errors.append(violation("provenance", f"semantic_contract.comparison_groups.{group['id']}", "contract references unknown rows", actual=sorted(missing)))
        unknown_metrics = set(group["metric_keys"]) - reference_columns.keys()
        if unknown_metrics:
            errors.append(violation("provenance", f"semantic_contract.comparison_groups.{group['id']}", "contract references unknown metrics", actual=sorted(unknown_metrics)))

    if case["input_tier"] == "raw_runs" and not candidate.get("aggregation_audit"):
        errors.append(violation("provenance", "aggregation_audit", "raw-run candidate must retain contributing run IDs"))

    counts = Counter(error["category"] for error in errors)
    scientific_errors = [error for error in errors if error["category"] in SCIENTIFIC_CATEGORIES]
    return {
        "case_id": case["id"],
        "passed_scientific_gate": not scientific_errors,
        "passed_full_contract": not errors,
        "violation_count": len(errors),
        "scientific_violation_count": len(scientific_errors),
        "category_counts": dict(sorted(counts.items())),
        "violations": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case", type=Path)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    report = evaluate(
        json.loads(args.reference.read_text()),
        json.loads(args.candidate.read_text()),
        json.loads(args.case.read_text()),
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed_full_contract"] else 1)


if __name__ == "__main__":
    main()
