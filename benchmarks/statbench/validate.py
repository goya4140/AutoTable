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
    return errors


def main() -> None:
    failures = {}
    for case_dir in sorted((HERE / "cases").iterdir()):
        if not case_dir.is_dir():
            continue
        case = json.loads((case_dir / "case.json").read_text())
        if case["id"] == "neurips24-diamond-atari":
            errors = validate_diamond(case_dir)
        else:
            errors = ["no validator registered"]
        if errors:
            failures[case["id"]] = errors
    report = {"passed": not failures, "cases": len(list((HERE / "cases").glob("*/case.json"))), "failures": failures}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
