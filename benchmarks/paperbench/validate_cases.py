#!/usr/bin/env python3
"""Validate PaperBench case files, hashes, and semantic-contract references."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REQUIRED_CASE_KEYS = {
    "schema_version",
    "id",
    "task",
    "input_tier",
    "venue",
    "year",
    "paper_url",
    "reference",
    "license",
    "semantic_contract",
}
REQUIRED_CONTRACT_KEYS = {
    "claim",
    "row_identity_key",
    "comparison_groups",
    "statistics",
    "allowed_transformations",
    "forbidden_inferences",
    "rendering_constraints",
    "inquiry_profile",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_case(case_dir: Path) -> list[str]:
    errors = []
    case = json.loads((case_dir / "case.json").read_text())
    spec = json.loads((case_dir / "x.json").read_text())
    missing = REQUIRED_CASE_KEYS - case.keys()
    if missing:
        errors.append(f"missing case keys: {sorted(missing)}")
        return errors
    if case["schema_version"] != "2.0":
        errors.append("schema_version must be 2.0")
    if case["task"] != "experimental-data-to-publication-table":
        errors.append("unexpected task")
    contract = case["semantic_contract"]
    if REQUIRED_CONTRACT_KEYS - contract.keys():
        errors.append(f"missing contract keys: {sorted(REQUIRED_CONTRACT_KEYS - contract.keys())}")
        return errors
    image = case_dir / case["reference"]["image"]
    if not image.exists() or digest(image) != case["reference"]["sha256"]:
        errors.append("reference image hash mismatch")
    row_key = contract["row_identity_key"]
    row_values = [row.get(row_key) for row in spec.get("rows", [])]
    if None in row_values or len(row_values) != len(set(row_values)):
        errors.append("row identity values must be present and unique")
    metric_columns = {column["key"] for column in spec.get("columns", []) if column.get("kind") == "metric"}
    for column in spec.get("columns", []):
        if column.get("kind") == "metric" and column.get("direction") not in {"min", "max"}:
            errors.append(f"metric {column.get('key')} lacks direction")
        if column.get("kind") == "metric" and "unit" not in column:
            errors.append(f"metric {column.get('key')} lacks unit")
    for group in contract["comparison_groups"]:
        unknown_rows = (set(group["row_values"]) | set(group.get("excluded_row_values", []))) - set(row_values)
        unknown_metrics = set(group["metric_keys"]) - metric_columns
        if unknown_rows:
            errors.append(f"comparison group {group['id']} has unknown rows: {sorted(unknown_rows)}")
        if unknown_metrics:
            errors.append(f"comparison group {group['id']} has unknown metrics: {sorted(unknown_metrics)}")
    field_ids = [field["id"] for field in contract["inquiry_profile"]["fields"]]
    if len(field_ids) != len(set(field_ids)):
        errors.append("inquiry field ids must be unique")
    for field in contract["inquiry_profile"]["fields"]:
        if field.get("answer_status") not in {"available", "unavailable"}:
            errors.append(f"inquiry field {field.get('id')} lacks a valid answer_status")
    for artifact in case.get("source_artifacts", []):
        if artifact.get("path"):
            path = case_dir / artifact["path"]
            if not path.exists() or digest(path) != artifact["sha256"]:
                errors.append(f"source artifact hash mismatch: {artifact['path']}")
    return errors


def main() -> None:
    failures = {}
    for case_dir in sorted((HERE / "cases").iterdir()):
        if case_dir.is_dir():
            errors = validate_case(case_dir)
            if errors:
                failures[case_dir.name] = errors
    report = {"passed": not failures, "cases": len(list((HERE / "cases").glob("*/case.json"))), "failures": failures}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
