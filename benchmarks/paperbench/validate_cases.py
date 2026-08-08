#!/usr/bin/env python3
"""Validate PaperBench case files, hashes, and semantic-contract references."""
from __future__ import annotations

import hashlib
import importlib.util
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


def load_raw_aggregator(schema_version: str):
    scripts = {
        "paper-table-observations-v1": "aggregate_observations.py",
        "paper-table-runs-v1": "aggregate_runs.py",
        "paper-table-crossfold-v1": "aggregate_crossfold.py",
    }
    if schema_version not in scripts:
        raise ValueError(f"unsupported raw input schema: {schema_version}")
    path = HERE.parents[1] / "skills/paper-table/scripts" / scripts[schema_version]
    spec = importlib.util.spec_from_file_location(f"paperbench_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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
    if case["input_tier"] == "raw_runs":
        descriptor = case.get("input")
        if not descriptor:
            errors.append("raw_runs case requires an input descriptor")
        else:
            input_path = case_dir / descriptor.get("path", "")
            if not input_path.is_file() or digest(input_path) != descriptor.get("sha256"):
                errors.append("raw input hash mismatch")
            else:
                try:
                    payload = json.loads(input_path.read_text())
                    if payload.get("schema_version") != descriptor.get("schema"):
                        errors.append("raw input schema mismatch")
                    recomputed = load_raw_aggregator(payload.get("schema_version")).aggregate(payload)
                    for key in ("columns", "rows", "aggregation_audit"):
                        if recomputed.get(key) != spec.get(key):
                            errors.append(f"raw input does not reproduce x.json {key}")
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    errors.append(f"raw input aggregation failed: {exc}")
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
