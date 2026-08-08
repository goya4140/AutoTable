#!/usr/bin/env python3
"""Validate VariationBench reproducibility and simulated-evidence isolation."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE_DIR = HERE / "cases/assumption-only-controlled"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expects_error(simulator, payload: dict, fragment: str) -> bool:
    try:
        simulator.simulate(payload)
    except ValueError as error:
        return fragment in str(error)
    return False


def validate_case() -> tuple[list[str], int]:
    errors = []
    case = json.loads((CASE_DIR / "case.json").read_text())
    for key in ("input", "expected_report", "table_spec"):
        descriptor = case[key]
        path = CASE_DIR / descriptor["path"]
        if not path.is_file() or digest(path) != descriptor["sha256"]:
            errors.append(f"artifact hash mismatch: {descriptor['path']}")
    if errors:
        return errors, 0
    builder = load(HERE / "build_case.py", "variationbench_builder")
    simulator = builder.load_simulator()
    payload = json.loads((CASE_DIR / case["input"]["path"]).read_text())
    expected = json.loads((CASE_DIR / case["expected_report"]["path"]).read_text())
    table = json.loads((CASE_DIR / case["table_spec"]["path"]).read_text())
    recomputed = simulator.simulate(payload)
    if recomputed != expected:
        errors.append("simulation report is not reproducible")
    if builder.table_spec(recomputed) != table:
        errors.append("scenario table is not reproducible from report")
    contract = recomputed["global_contract"]
    if contract["observed"] or contract["eligible_for_inference"] or contract["eligible_for_verified_table"]:
        errors.append("simulated evidence isolation contract failed")
    if table["observed"] or table["emphasis"] != {"best": "none", "second": "none", "scope": "all"}:
        errors.append("scenario table appears observed or rank-emphasized")
    if any(row.get("rank_eligible") is not False for row in table["rows"]):
        errors.append("scenario row became rank eligible")

    mutations = []
    reordered = copy.deepcopy(payload)
    reordered["cells"].reverse()
    mutations.append(simulator.simulate(reordered) == recomputed)
    changed_seed = copy.deepcopy(payload)
    changed_seed["scenario"]["seed"] += 1
    changed = simulator.simulate(changed_seed)
    mutations.append(changed["cells"][0]["simulated_summary"]["draw_order_sha256"] != recomputed["cells"][0]["simulated_summary"]["draw_order_sha256"])
    no_seed = copy.deepcopy(payload)
    no_seed["scenario"].pop("seed")
    mutations.append(expects_error(simulator, no_seed, "scenario.seed"))
    too_few_draws = copy.deepcopy(payload)
    too_few_draws["scenario"]["draws"] = 100
    mutations.append(expects_error(simulator, too_few_draws, "scenario.draws"))
    inferred_request = copy.deepcopy(payload)
    inferred_request["scenario"]["request_source"] = "agent_inferred"
    mutations.append(expects_error(simulator, inferred_request, "author_requested"))
    inference_purpose = copy.deepcopy(payload)
    inference_purpose["scenario"]["purpose"] = "significance"
    mutations.append(expects_error(simulator, inference_purpose, "illustrative_possible_variation_only"))
    no_scale_source = copy.deepcopy(payload)
    no_scale_source["cells"][0]["model"].pop("scale_source_detail")
    mutations.append(expects_error(simulator, no_scale_source, "scale_source"))
    zero_sd = copy.deepcopy(payload)
    zero_sd["cells"][0]["model"]["scale_parameter"] = 0
    mutations.append(expects_error(simulator, zero_sd, "scale_parameter"))
    wrong_scale_parameterization = copy.deepcopy(payload)
    wrong_scale_parameterization["cells"][0]["model"]["scale_parameterization"] = "distribution_sd"
    mutations.append(expects_error(simulator, wrong_scale_parameterization, "parent_normal_sd_before_truncation"))
    invalid_bounds = copy.deepcopy(payload)
    invalid_bounds["cells"][0]["model"]["lower_bound"] = 101
    mutations.append(expects_error(simulator, invalid_bounds, "lower_bound"))
    normal_bounds = copy.deepcopy(payload)
    normal_bounds["cells"][0]["model"]["family"] = "normal"
    normal_bounds["cells"][0]["model"]["scale_parameterization"] = "distribution_sd"
    mutations.append(expects_error(simulator, normal_bounds, "cannot declare bounds"))
    duplicate = copy.deepcopy(payload)
    duplicate["cells"].append(copy.deepcopy(duplicate["cells"][0]))
    mutations.append(expects_error(simulator, duplicate, "duplicate"))
    wrong_count = copy.deepcopy(payload)
    wrong_count["cells"][0]["model"]["future_run_count"] = 2
    mutations.append(expects_error(simulator, wrong_count, "equal to one"))
    false_observed = copy.deepcopy(payload)
    false_observed["provenance"]["observed"] = True
    mutations.append(expects_error(simulator, false_observed, "cannot be true"))
    mutations.append(all(cell["status"] == "simulated_scenario_only" and not cell["eligible_for_ranking"] for cell in recomputed["cells"]))
    mutations.append(
        all(row["status"] == "SIMULATED" for row in table["rows"])
        and "SIMULATED" in table["title"]
        and table["caption"].startswith("SIMULATED SCENARIO")
    )
    if not all(mutations):
        errors.append("one or more simulation-safety mutations were not handled")
    return errors, len(mutations)


def main() -> None:
    errors, mutations = validate_case()
    report = {"passed": not errors, "cases": 1, "controlled_safety_mutations": mutations, "failures": errors}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
