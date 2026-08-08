#!/usr/bin/env python3
"""Validate DataPlanBench artifacts and controlled acquisition-safety mutations."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE_DIR = HERE / "cases/paired-precision-controlled"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expects_error(planner, payload: dict, fragment: str) -> bool:
    try:
        planner.plan(payload)
    except ValueError as error:
        return fragment in str(error)
    return False


def validate_case() -> tuple[list[str], int]:
    errors = []
    case = json.loads((CASE_DIR / "case.json").read_text())
    for descriptor_key in ("input", "expected_report", "table_spec"):
        descriptor = case[descriptor_key]
        path = CASE_DIR / descriptor["path"]
        if not path.is_file() or digest(path) != descriptor["sha256"]:
            errors.append(f"artifact hash mismatch: {descriptor['path']}")
    if errors:
        return errors, 0
    builder = load(HERE / "build_case.py", "dataplanbench_builder")
    planner = builder.load_planner()
    payload = json.loads((CASE_DIR / case["input"]["path"]).read_text())
    expected = json.loads((CASE_DIR / case["expected_report"]["path"]).read_text())
    table = json.loads((CASE_DIR / case["table_spec"]["path"]).read_text())
    recomputed = planner.plan(payload)
    if recomputed != expected:
        errors.append("data-acquisition report is not reproducible from raw runs")
    if builder.table_spec(recomputed) != table:
        errors.append("acquisition table is not reproducible from the report")
    if recomputed["completeness"]["repair_count"] != 4:
        errors.append("expected three missing pairs and one invalid metric repair")
    request = recomputed["precision"]["request"]
    if request.get("provisional_common_total_runs") != 14 or request.get("additional_common_run_ids") != 9:
        errors.append("provisional paired precision request changed")
    if not recomputed["completeness"]["requires_replan_after_repair"] or not recomputed["precision"]["provisional"]:
        errors.append("repair-first provisional status disappeared")

    mutations = []
    duplicate = copy.deepcopy(payload)
    duplicate["runs"].append(dict(duplicate["runs"][0]))
    mutations.append(expects_error(planner, duplicate, "duplicate run id"))
    dependent = copy.deepcopy(payload)
    dependent["independence"] = "unknown"
    mutations.append(expects_error(planner, dependent, "explicitly declared"))
    missing_target = copy.deepcopy(payload)
    missing_target["planning"]["target_half_widths"] = {}
    mutations.append(expects_error(planner, missing_target, "target_half_widths"))
    no_assumption = copy.deepcopy(payload)
    no_assumption["planning"].pop("variance_assumption")
    mutations.append(expects_error(planner, no_assumption, "variance_assumption"))
    no_interval_assumption = copy.deepcopy(payload)
    no_interval_assumption["planning"].pop("interval_assumption")
    mutations.append(expects_error(planner, no_interval_assumption, "interval_assumption"))
    wrong_estimand = copy.deepcopy(payload)
    wrong_estimand["planning"]["estimand"] = "paired_difference"
    mutations.append(expects_error(planner, wrong_estimand, "estimand must be group_mean"))
    hidden_run = copy.deepcopy(payload)
    hidden_run["pairing"]["expected_run_ids"] = [0, 1, 2, 3]
    mutations.append(expects_error(planner, hidden_run, "outside expected_run_ids"))
    hidden_group = copy.deepcopy(payload)
    hidden_group["pairing"]["expected_groups"].pop()
    mutations.append(expects_error(planner, hidden_group, "outside expected_groups"))
    zero_cell = next(cell for cell in recomputed["precision"]["cells"] if cell["status"] == "zero_pilot_variance_requires_review")
    mutations.append(zero_cell["required_total_runs"] is None and not zero_cell["target_met"])
    mutations.append(len(recomputed["completeness"]["invalid_metric_requests"]) == 1)
    mutations.append(bool(recomputed["questions_for_author"]) and recomputed["completeness"]["requires_replan_after_repair"])
    if not all(mutations):
        errors.append("one or more acquisition-safety mutations were not handled")
    return errors, len(mutations)


def main() -> None:
    errors, mutations = validate_case()
    report = {"passed": not errors, "cases": 1, "controlled_safety_mutations": mutations, "failures": errors}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
