#!/usr/bin/env python3
"""Validate InferenceBench reports, rendered-table consistency, and safety mutations."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE_DIR = HERE / "cases/tunetables-top5"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expects_error(analyzer, payload: dict, fragment: str) -> bool:
    try:
        analyzer.analyze(payload)
    except ValueError as error:
        return fragment in str(error)
    return False


def validate_case() -> list[str]:
    errors = []
    case = json.loads((CASE_DIR / "case.json").read_text())
    for descriptor_key in ("input", "expected_report", "table_spec"):
        descriptor = case[descriptor_key]
        path = CASE_DIR / descriptor["path"]
        if not path.is_file() or digest(path) != descriptor["sha256"]:
            errors.append(f"artifact hash mismatch: {descriptor['path']}")
    if errors:
        return errors
    builder = load(HERE / "build_tunetables_case.py", "inferencebench_builder")
    analyzer = builder.load_analyzer()
    payload = json.loads((CASE_DIR / case["input"]["path"]).read_text())
    expected = json.loads((CASE_DIR / case["expected_report"]["path"]).read_text())
    table = json.loads((CASE_DIR / case["table_spec"]["path"]).read_text())
    recomputed = analyzer.analyze(payload)
    if recomputed != expected:
        errors.append("expected report is not reproducible from paired input")
    if builder.table_spec(recomputed) != table:
        errors.append("inference table is not reproducible from the report")
    if recomputed["design"]["n_units"] != 98 or len(recomputed["results"]) != 4:
        errors.append("expected 98 paired datasets and four comparisons")
    mutations = []
    missing = copy.deepcopy(payload)
    missing["records"].pop()
    mutations.append(expects_error(analyzer, missing, "complete baseline unit set"))
    unknown = copy.deepcopy(payload)
    unknown["design"]["unit_independence"] = "unknown"
    mutations.append(expects_error(analyzer, unknown, "independent paired units"))
    uncorrected = copy.deepcopy(payload)
    uncorrected["multiplicity"]["correction"] = "none"
    mutations.append(expects_error(analyzer, uncorrected, "require Holm correction"))
    no_exchangeability = copy.deepcopy(payload)
    no_exchangeability["test"].pop("exchangeability_rationale")
    mutations.append(expects_error(analyzer, no_exchangeability, "exchangeability declaration and rationale"))
    pseudoreplicated = copy.deepcopy(payload)
    pseudoreplicated["design"]["cluster_key"] = "study_cluster"
    for record in pseudoreplicated["records"]:
        record["study_cluster"] = "shared"
    mutations.append(expects_error(analyzer, pseudoreplicated, "nested within clusters"))
    if not all(mutations):
        errors.append("one or more inferential safety mutations were not rejected")
    return errors


def main() -> None:
    errors = validate_case()
    report = {"passed": not errors, "cases": 1, "controlled_safety_mutations": 5, "failures": errors}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
