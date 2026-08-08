import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load():
    path = ROOT / "skills/paper-table/scripts/simulate_variation.py"
    spec = importlib.util.spec_from_file_location("simulate_variation_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload():
    return {
        "schema_version": "paper-table-simulated-variation-v1",
        "scenario": {
            "label": "Author-requested deployment variability illustration",
            "request_source": "author_requested",
            "purpose": "illustrative_possible_variation_only",
            "draws": 5000,
            "seed": 20260808,
            "interval_mass": 0.9,
        },
        "cells": [
            {
                "identity": {"dataset": "D", "method": "A"},
                "metric": "accuracy",
                "direction": "max",
                "unit": "%",
                "observed_value": 80.0,
                "model": {
                    "family": "truncated_normal",
                    "scale_parameter": 4.0,
                    "scale_parameterization": "parent_normal_sd_before_truncation",
                    "scale_source": "author_assumption",
                    "scale_source_detail": "Planning assumption supplied by the author; no repeated runs are available.",
                    "lower_bound": 0.0,
                    "upper_bound": 100.0,
                    "future_target": "future_single_run",
                    "future_run_count": 1,
                },
            },
            {
                "identity": {"dataset": "D", "method": "B"},
                "metric": "accuracy",
                "direction": "max",
                "unit": "%",
                "observed_value": 82.0,
                "model": {
                    "family": "normal",
                    "scale_parameter": 4.0,
                    "scale_parameterization": "distribution_sd",
                    "scale_source": "external_domain_evidence",
                    "scale_source_detail": "Pinned prior study DOI:10.example/variation.",
                    "future_target": "future_mean_of_independent_runs",
                    "future_run_count": 4,
                },
            },
        ],
        "provenance": {"status": "assumption_only", "observed_source": "author point estimates"},
    }


def test_simulation_is_deterministic_order_invariant_and_permanently_noninferential():
    simulator = load()
    first = simulator.simulate(payload())
    second_payload = payload()
    second_payload["cells"].reverse()
    second = simulator.simulate(second_payload)
    assert first == second
    assert not first["global_contract"]["observed"]
    assert not first["global_contract"]["eligible_for_inference"]
    assert not first["global_contract"]["eligible_for_verified_table"]
    assert all(not cell["observed"] and not cell["eligible_for_ranking"] for cell in first["cells"])
    assert first["scenario"]["label"].startswith("SIMULATED SCENARIO")
    assert first["provenance"]["observed"] is False and first["provenance"]["verified"] is False


def test_mean_of_four_independent_normal_runs_has_about_half_distribution_sd():
    report = load().simulate(payload())
    cells = {cell["identity"]["method"]: cell for cell in report["cells"]}
    assert cells["A"]["simulated_summary"]["sd"] == pytest.approx(4.0, rel=0.04)
    assert cells["B"]["simulated_summary"]["sd"] == pytest.approx(2.0, rel=0.04)
    assert 0 <= cells["A"]["simulated_summary"]["lower"] < cells["A"]["simulated_summary"]["upper"] <= 100


def test_seed_changes_draw_hash_but_preserves_contract():
    simulator = load()
    first = simulator.simulate(payload())
    changed = payload()
    changed["scenario"]["seed"] += 1
    second = simulator.simulate(changed)
    assert first["cells"][0]["simulated_summary"]["draw_order_sha256"] != second["cells"][0]["simulated_summary"]["draw_order_sha256"]
    assert first["global_contract"] == second["global_contract"]


def test_excessive_expected_truncated_rejection_work_is_rejected():
    data = payload()
    model = data["cells"][0]["model"]
    model["future_target"] = "future_mean_of_independent_runs"
    model["future_run_count"] = 100
    model["lower_bound"] = 79.98
    model["upper_bound"] = 80.02
    with pytest.raises(ValueError, match="expected rejection-sampling work"):
        load().simulate(data)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item["scenario"].pop("seed"), "scenario.seed"),
        (lambda item: item["scenario"].update({"draws": 99}), "scenario.draws"),
        (lambda item: item["scenario"].update({"request_source": "agent_inferred"}), "author_requested"),
        (lambda item: item["cells"][0]["model"].pop("scale_source_detail"), "scale_source"),
        (lambda item: item["cells"][0]["model"].update({"scale_parameter": 0}), "scale_parameter"),
        (lambda item: item["cells"][0]["model"].update({"scale_parameterization": "distribution_sd"}), "parent_normal_sd_before_truncation"),
        (lambda item: item["cells"][0]["model"].update({"lower_bound": 101}), "lower_bound"),
        (lambda item: item["cells"][1]["model"].update({"lower_bound": 0}), "cannot declare bounds"),
        (lambda item: item["cells"].append(copy.deepcopy(item["cells"][0])), "duplicate"),
        (lambda item: item["provenance"].update({"observed": True}), "cannot be true"),
    ],
)
def test_unsafe_or_incomplete_assumptions_fail(mutation, message):
    data = payload()
    mutation(data)
    with pytest.raises(ValueError, match=message):
        load().simulate(data)


def test_report_contains_no_inferential_or_ranking_outputs():
    report = load().simulate(payload())
    def keys(value):
        if isinstance(value, dict):
            return set(value) | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value)) if value else set()
        return set()
    output_keys = keys(report)
    for forbidden in ("p_value", "adjusted_p", "significant", "winner", "best_method", "rank_value"):
        assert forbidden not in output_keys
    assert report["global_contract"]["eligible_for_significance_markers"] is False
