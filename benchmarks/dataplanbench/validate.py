#!/usr/bin/env python3
"""Validate DataPlanBench artifacts and controlled acquisition-safety mutations."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MEAN_CASE_DIR = HERE / "cases/paired-precision-controlled"
DIFFERENCE_CASE_DIR = HERE / "cases/paired-difference-controlled"


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
    case = json.loads((MEAN_CASE_DIR / "case.json").read_text())
    for descriptor_key in ("input", "expected_report", "table_spec"):
        descriptor = case[descriptor_key]
        path = MEAN_CASE_DIR / descriptor["path"]
        if not path.is_file() or digest(path) != descriptor["sha256"]:
            errors.append(f"artifact hash mismatch: {descriptor['path']}")
    if errors:
        return errors, 0
    builder = load(HERE / "build_case.py", "dataplanbench_builder")
    planner = builder.load_planner()
    payload = json.loads((MEAN_CASE_DIR / case["input"]["path"]).read_text())
    expected = json.loads((MEAN_CASE_DIR / case["expected_report"]["path"]).read_text())
    table = json.loads((MEAN_CASE_DIR / case["table_spec"]["path"]).read_text())
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
    influential = copy.deepcopy(payload)
    for row in influential["runs"]:
        if row["dataset"] == "Dataset-1" and row["method"] == "Baseline":
            row["accuracy_pp"] = 100.0 if row["seed"] == 4 else 70.0
    influential_report = planner.plan(influential)
    influential_cell = next(
        cell for cell in influential_report["precision"]["cells"]
        if cell["group"] == {"dataset": "Dataset-1", "method": "Baseline"}
    )
    mutations.append(
        influential_cell["pilot_stability"]["status"] == "review_required"
        and influential_cell["pilot_stability"]["leave_one_run_out"]["zero_variance_after_omitting_run_ids"] == [4]
    )
    mutations.append(any("without deleting observations post hoc" in question for question in influential_report["questions_for_author"]))
    if not all(mutations):
        errors.append("one or more acquisition-safety mutations were not handled")
    return errors, len(mutations)


def validate_paired_difference_case() -> tuple[list[str], int]:
    errors = []
    case = json.loads((DIFFERENCE_CASE_DIR / "case.json").read_text())
    for descriptor_key in ("input", "expected_report", "table_spec"):
        descriptor = case[descriptor_key]
        path = DIFFERENCE_CASE_DIR / descriptor["path"]
        if not path.is_file() or digest(path) != descriptor["sha256"]:
            errors.append(f"artifact hash mismatch: paired-difference/{descriptor['path']}")
    if errors:
        return errors, 0
    builder = load(HERE / "build_case.py", "dataplanbench_difference_builder")
    planner = builder.load_planner(builder.DIFFERENCE_PLANNER_PATH)
    payload = json.loads((DIFFERENCE_CASE_DIR / case["input"]["path"]).read_text())
    expected = json.loads((DIFFERENCE_CASE_DIR / case["expected_report"]["path"]).read_text())
    table = json.loads((DIFFERENCE_CASE_DIR / case["table_spec"]["path"]).read_text())
    recomputed = planner.plan(payload)
    if recomputed != expected:
        errors.append("paired-difference report is not reproducible from raw runs")
    if builder.paired_difference_table_spec(recomputed) != table:
        errors.append("paired-difference table is not reproducible from the report")
    if recomputed["completeness"]["repair_count"] != 4:
        errors.append("paired-difference case must expose three missing cells and one invalid metric")
    request = recomputed["precision"]["request"]
    if request.get("provisional_common_total_pairs") != 7 or request.get("additional_common_run_ids") != 2:
        errors.append("paired-difference provisional common-pair request changed")
    dataset_one_b = next(
        cell for cell in recomputed["precision"]["cells"]
        if cell["context"] == {"dataset": "Dataset-1"} and cell["candidate"] == "Method-B"
    )
    if dataset_one_b["paired_difference_sd"] != 1.5811388300841898 or dataset_one_b["required_total_pairs"] != 7:
        errors.append("paired-difference SD or required-pair calculation changed")
    if recomputed["precision"]["estimand"] != "paired_mean_difference" or not recomputed["precision"]["provisional"]:
        errors.append("paired estimand or provisional status disappeared")

    mutations = []
    duplicate = copy.deepcopy(payload)
    duplicate["runs"].append(dict(duplicate["runs"][0]))
    mutations.append(expects_error(planner, duplicate, "duplicate run id"))
    dependent = copy.deepcopy(payload)
    dependent["independence"] = "unknown"
    mutations.append(expects_error(planner, dependent, "explicitly declared"))
    wrong_estimand = copy.deepcopy(payload)
    wrong_estimand["planning"]["estimand"] = "group_mean"
    mutations.append(expects_error(planner, wrong_estimand, "paired_mean_difference"))
    no_variance = copy.deepcopy(payload)
    no_variance["planning"].pop("variance_assumption")
    mutations.append(expects_error(planner, no_variance, "variance_assumption"))
    no_interval = copy.deepcopy(payload)
    no_interval["planning"].pop("interval_assumption")
    mutations.append(expects_error(planner, no_interval, "interval_assumption"))
    hidden_id = copy.deepcopy(payload)
    hidden_id["pairing"]["expected_run_ids"] = [0, 1, 2, 3]
    mutations.append(expects_error(planner, hidden_id, "outside expected_run_ids"))
    hidden_context = copy.deepcopy(payload)
    hidden_context["pairing"]["expected_contexts"] = [{"dataset": "Dataset-1"}]
    mutations.append(expects_error(planner, hidden_context, "outside expected_contexts"))
    hidden_method = copy.deepcopy(payload)
    hidden_method["pairing"]["candidates"] = ["Method-A"]
    mutations.append(expects_error(planner, hidden_method, "outside baseline and candidates"))
    zero_difference = copy.deepcopy(payload)
    baseline_values = {
        (row["dataset"], row["seed"]): row["accuracy_pp"]
        for row in zero_difference["runs"] if row["method"] == "Baseline"
    }
    for row in zero_difference["runs"]:
        if row["dataset"] == "Dataset-1" and row["method"] == "Method-B":
            row["accuracy_pp"] = baseline_values[(row["dataset"], row["seed"])] + 2
    zero_report = planner.plan(zero_difference)
    zero_cell = next(
        cell for cell in zero_report["precision"]["cells"]
        if cell["context"] == {"dataset": "Dataset-1"} and cell["candidate"] == "Method-B"
    )
    mutations.append(zero_cell["required_total_pairs"] is None and not zero_cell["target_met"])
    lower_better = copy.deepcopy(payload)
    lower_better["metrics"][0]["direction"] = "min"
    lower_report = planner.plan(lower_better)
    original_cell = next(cell for cell in recomputed["precision"]["cells"] if cell["candidate"] == "Method-A")
    reversed_cell = next(cell for cell in lower_report["precision"]["cells"] if cell["candidate"] == "Method-A")
    mutations.append(reversed_cell["mean_improvement"] == -original_cell["mean_improvement"])
    mutations.append(bool(recomputed["questions_for_author"]) and recomputed["completeness"]["requires_replan_after_repair"])
    mutations.append(len(recomputed["completeness"]["invalid_metric_requests"]) == 1)
    influential = copy.deepcopy(payload)
    baseline_values = {
        (row["dataset"], row["seed"]): row["accuracy_pp"]
        for row in influential["runs"] if row["method"] == "Baseline"
    }
    for row in influential["runs"]:
        if row["dataset"] == "Dataset-1" and row["method"] == "Method-B":
            row["accuracy_pp"] = baseline_values[(row["dataset"], row["seed"])] + (20 if row["seed"] == 4 else 2)
    influential_report = planner.plan(influential)
    influential_cell = next(
        cell for cell in influential_report["precision"]["cells"]
        if cell["context"] == {"dataset": "Dataset-1"} and cell["candidate"] == "Method-B"
    )
    mutations.append(
        influential_cell["pilot_stability"]["status"] == "review_required"
        and influential_cell["pilot_stability"]["leave_one_run_out"]["zero_variance_after_omitting_run_ids"] == [4]
    )
    mutations.append(any("without deleting observations post hoc" in question for question in influential_report["questions_for_author"]))
    if not all(mutations):
        errors.append("one or more paired-difference safety mutations were not handled")
    return errors, len(mutations)


def main() -> None:
    mean_errors, mean_mutations = validate_case()
    difference_errors, difference_mutations = validate_paired_difference_case()
    errors = mean_errors + difference_errors
    report = {
        "passed": not errors,
        "cases": 2,
        "controlled_safety_mutations": mean_mutations + difference_mutations,
        "case_mutations": {"group_mean": mean_mutations, "paired_mean_difference": difference_mutations},
        "failures": errors,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
