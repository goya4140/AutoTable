#!/usr/bin/env python3
"""Validate InferenceBench reports, rendered-table consistency, and safety mutations."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
TUNETABLES_DIR = HERE / "cases/tunetables-top5"
CLUSTERED_DIR = HERE / "cases/clustered-controlled"
MULTIMETHOD_DIR = HERE / "cases/tunetables-multimethod"


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


def validate_tunetables() -> tuple[list[str], int]:
    errors = []
    case = json.loads((TUNETABLES_DIR / "case.json").read_text())
    for descriptor_key in ("input", "expected_report", "table_spec"):
        descriptor = case[descriptor_key]
        path = TUNETABLES_DIR / descriptor["path"]
        if not path.is_file() or digest(path) != descriptor["sha256"]:
            errors.append(f"artifact hash mismatch: {descriptor['path']}")
    if errors:
        return errors, 0
    builder = load(HERE / "build_tunetables_case.py", "inferencebench_builder")
    analyzer = builder.load_analyzer()
    payload = json.loads((TUNETABLES_DIR / case["input"]["path"]).read_text())
    expected = json.loads((TUNETABLES_DIR / case["expected_report"]["path"]).read_text())
    table = json.loads((TUNETABLES_DIR / case["table_spec"]["path"]).read_text())
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
    return errors, len(mutations)


def validate_clustered() -> tuple[list[str], int]:
    errors = []
    case = json.loads((CLUSTERED_DIR / "case.json").read_text())
    for descriptor_key in ("input", "expected_report", "sensitivity_report", "table_spec"):
        descriptor = case[descriptor_key]
        path = CLUSTERED_DIR / descriptor["path"]
        if not path.is_file() or digest(path) != descriptor["sha256"]:
            errors.append(f"clustered artifact hash mismatch: {descriptor['path']}")
    if errors:
        return errors, 0
    builder = load(HERE / "build_clustered_case.py", "inferencebench_clustered_builder")
    analyzer = builder.load_analyzer()
    payload = json.loads((CLUSTERED_DIR / case["input"]["path"]).read_text())
    expected = json.loads((CLUSTERED_DIR / case["expected_report"]["path"]).read_text())
    sensitivity = json.loads((CLUSTERED_DIR / case["sensitivity_report"]["path"]).read_text())
    table = json.loads((CLUSTERED_DIR / case["table_spec"]["path"]).read_text())
    recomputed = analyzer.analyze(payload)
    sensitivity_recomputed = analyzer.analyze(builder.build_input("unit_weighted_mean"))
    if recomputed != expected:
        errors.append("clustered report is not reproducible from paired input")
    if sensitivity_recomputed != sensitivity:
        errors.append("unit-weighted sensitivity report is not reproducible")
    if builder.table_spec(recomputed, sensitivity_recomputed) != table:
        errors.append("clustered inference table is not reproducible from both reports")
    if recomputed["design"]["n_units"] != 28 or recomputed["design"]["n_clusters"] != 8:
        errors.append("expected 28 paired tasks nested in eight independent studies")
    if recomputed["design"].get("cluster_size_summary") != {"minimum": 2, "maximum": 5, "unequal": True}:
        errors.append("unequal cluster-size diagnostic disappeared")
    if recomputed.get("diagnostics", {}).get("best_case_two_sided_exact_p_resolution") != 0.0078125:
        errors.append("exact cluster sign-flip resolution diagnostic is wrong")
    if not recomputed.get("diagnostics", {}).get("few_clusters_warning"):
        errors.append("few-cluster warning disappeared")
    primary = {row["method"]: row for row in recomputed["results"]}
    alternate = {row["method"]: row for row in sensitivity_recomputed["results"]}
    if not (primary["Volume-biased"]["mean_improvement"] < 0 < alternate["Volume-biased"]["mean_improvement"]):
        errors.append("controlled unequal-size estimand reversal disappeared")
    if any(row["randomization_unit"] != "cluster" or row["bootstrap_resampling_unit"] != "cluster" for row in recomputed["results"]):
        errors.append("clustered inference did not preserve cluster-level randomization and resampling")

    mutations = []
    missing = copy.deepcopy(payload)
    missing["records"].pop()
    mutations.append(expects_error(analyzer, missing, "complete baseline unit set"))
    unknown = copy.deepcopy(payload)
    unknown["design"]["cluster_independence"] = "unknown"
    mutations.append(expects_error(analyzer, unknown, "independent clusters"))
    no_estimand = copy.deepcopy(payload)
    no_estimand["design"].pop("cluster_estimand")
    mutations.append(expects_error(analyzer, no_estimand, "cluster_estimand"))
    no_exchangeability = copy.deepcopy(payload)
    no_exchangeability["test"].pop("exchangeability_rationale")
    mutations.append(expects_error(analyzer, no_exchangeability, "cluster-sign exchangeability"))
    wrong_randomization = copy.deepcopy(payload)
    wrong_randomization["test"]["name"] = "paired_sign_flip_mean"
    mutations.append(expects_error(analyzer, wrong_randomization, "cluster_sign_flip_mean"))
    uncorrected = copy.deepcopy(payload)
    uncorrected["multiplicity"]["correction"] = "none"
    mutations.append(expects_error(analyzer, uncorrected, "require Holm correction"))
    if not all(mutations):
        errors.append("one or more clustered safety mutations were not rejected")
    return errors, len(mutations)


def validate_multimethod() -> tuple[list[str], int]:
    errors = []
    case = json.loads((MULTIMETHOD_DIR / "case.json").read_text())
    for descriptor_key in ("input", "expected_report", "table_spec"):
        descriptor = case[descriptor_key]
        path = MULTIMETHOD_DIR / descriptor["path"]
        if not path.is_file() or digest(path) != descriptor["sha256"]:
            errors.append(f"multi-method artifact hash mismatch: {descriptor['path']}")
    if errors:
        return errors, 0
    builder = load(HERE / "build_multimethod_case.py", "inferencebench_multimethod_builder")
    analyzer = builder.load_analyzer()
    payload = json.loads((MULTIMETHOD_DIR / case["input"]["path"]).read_text())
    expected = json.loads((MULTIMETHOD_DIR / case["expected_report"]["path"]).read_text())
    table = json.loads((MULTIMETHOD_DIR / case["table_spec"]["path"]).read_text())
    recomputed = analyzer.analyze(payload)
    if recomputed != expected:
        errors.append("multi-method report is not reproducible from complete-block input")
    if builder.table_spec(recomputed) != table:
        errors.append("multi-method inference table is not reproducible from the report")
    if recomputed["design"]["n_blocks"] != 98 or recomputed["design"]["n_methods"] != 5:
        errors.append("expected five methods across 98 complete dataset blocks")
    if recomputed["omnibus"]["blocks_with_ties"] != 35:
        errors.append("tie-aware rank audit changed")
    if not recomputed["omnibus"]["reject_global_null"]:
        errors.append("pinned multi-method omnibus no longer rejects")

    paired = json.loads((TUNETABLES_DIR / "expected_report.json").read_text())
    paired_results = {row["method"]: row for row in paired["results"]}
    for result in recomputed["posthoc"]["results"]:
        reference = paired_results[result["method"]]
        for key in ("mean_improvement", "improvement_ci", "p_raw", "p_adjusted", "reject_null"):
            if result[key] != reference[key]:
                errors.append(f"multi-method post-hoc drift for {result['method']} field {key}")

    mutations = []
    incomplete = copy.deepcopy(payload)
    incomplete["records"].pop()
    mutations.append(expects_error(analyzer, incomplete, "incomplete"))
    dependent = copy.deepcopy(payload)
    dependent["design"]["block_independence"] = "unknown"
    mutations.append(expects_error(analyzer, dependent, "complete, independent blocks"))
    no_tie_policy = copy.deepcopy(payload)
    no_tie_policy["omnibus"].pop("rank_tie_policy")
    mutations.append(expects_error(analyzer, no_tie_policy, "rank_tie_policy"))
    no_global_exchangeability = copy.deepcopy(payload)
    no_global_exchangeability["omnibus"].pop("exchangeability_rationale")
    mutations.append(expects_error(analyzer, no_global_exchangeability, "omnibus requires"))
    late_baseline = copy.deepcopy(payload)
    late_baseline["posthoc"]["baseline_selection_timing"] = "chosen_after_results"
    mutations.append(expects_error(analyzer, late_baseline, "predeclared"))
    cherry_picked = copy.deepcopy(payload)
    cherry_picked["posthoc"]["candidates"].pop()
    mutations.append(expects_error(analyzer, cherry_picked, "every other method"))
    no_gate = copy.deepcopy(payload)
    no_gate["posthoc"]["gatekeeping"] = "none"
    mutations.append(expects_error(analyzer, no_gate, "require omnibus rejection"))
    uncorrected = copy.deepcopy(payload)
    uncorrected["posthoc"]["multiplicity"]["correction"] = "none"
    mutations.append(expects_error(analyzer, uncorrected, "Holm correction"))
    global_null = copy.deepcopy(payload)
    for record in global_null["records"]:
        record[global_null["score_key"]] = 1.0
    null_report = analyzer.analyze(global_null)
    mutations.append(
        null_report["omnibus"]["p_value"] == 1.0
        and not null_report["omnibus"]["reject_global_null"]
        and all(not row["significance_marker_eligible"] and not row["reject_null"] for row in null_report["posthoc"]["results"])
    )
    if not all(mutations):
        errors.append("one or more multi-method safety mutations were not rejected")
    return errors, len(mutations)


def main() -> None:
    tunetables_errors, tunetables_mutations = validate_tunetables()
    clustered_errors, clustered_mutations = validate_clustered()
    multimethod_errors, multimethod_mutations = validate_multimethod()
    errors = [*tunetables_errors, *clustered_errors, *multimethod_errors]
    report = {
        "passed": not errors,
        "cases": 3,
        "controlled_safety_mutations": tunetables_mutations + clustered_mutations + multimethod_mutations,
        "failures": errors,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
