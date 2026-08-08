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


def main() -> None:
    tunetables_errors, tunetables_mutations = validate_tunetables()
    clustered_errors, clustered_mutations = validate_clustered()
    errors = [*tunetables_errors, *clustered_errors]
    report = {
        "passed": not errors,
        "cases": 2,
        "controlled_safety_mutations": tunetables_mutations + clustered_mutations,
        "failures": errors,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
