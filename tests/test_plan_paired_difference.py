import copy
import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load():
    path = ROOT / "skills/paper-table/scripts/plan_paired_difference.py"
    spec = importlib.util.spec_from_file_location("plan_paired_difference_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload():
    return {
        "schema_version": "paper-table-paired-difference-plan-v1",
        "method_key": "method",
        "context_keys": ["dataset"],
        "metrics": [{"key": "score", "direction": "max", "unit": "points"}],
        "runs": [
            {"dataset": "D", "method": method, "run": run, "score": value}
            for method, values in {
                "Base": [10.0, 20.0, 30.0, 40.0, 50.0],
                "A": [12.0, 21.0, 34.0, 43.0],
                "B": [11.0, 21.0, 31.0, 41.0, 51.0],
            }.items()
            for run, value in enumerate(values)
        ],
        "run_id_key": "run",
        "repeat_unit": "independent training seed",
        "independence": "independent",
        "pairing": {
            "mode": "baseline_vs_all_fixed_ids",
            "baseline": "Base",
            "candidates": ["A", "B"],
            "expected_contexts": [{"dataset": "D"}],
            "expected_run_ids": [0, 1, 2, 3, 4],
        },
        "planning": {
            "estimand": "paired_mean_difference",
            "confidence_level": 0.95,
            "target_half_widths": {"score": 1.5},
            "minimum_pilot_pairs": 5,
            "maximum_total_pairs": 30,
            "variance_assumption": "pilot_paired_difference_sd_stable_for_planning_only",
            "interval_assumption": "t_interval_appropriate_for_paired_difference_distribution",
        },
    }


def test_pairs_are_aligned_and_missing_existing_cell_is_repaired_first():
    report = load().plan(payload())
    assert report["completeness"]["repair_count"] == 1
    assert report["completeness"]["repair_requests"][0]["method"] == "A"
    cells = {cell["candidate"]: cell for cell in report["precision"]["cells"]}
    assert cells["A"]["paired_run_ids"] == [0, 1, 2, 3]
    assert cells["A"]["mean_improvement"] == pytest.approx(2.5)
    assert cells["A"]["paired_difference_sd"] == pytest.approx(1.2909944487358056)
    assert cells["A"]["status"] == "collect_minimum_pilot_then_replan"
    assert cells["B"]["mean_improvement"] == 1.0
    assert cells["B"]["status"] == "zero_pilot_difference_variance_requires_review"
    assert not cells["B"]["target_met"]
    assert report["precision"]["request"]["additional_common_run_ids"] == 0


def test_lower_is_better_is_oriented_as_positive_candidate_improvement():
    data = payload()
    data["metrics"][0]["direction"] = "min"
    report = load().plan(data)
    cell = next(cell for cell in report["precision"]["cells"] if cell["candidate"] == "A")
    assert cell["mean_improvement"] == pytest.approx(-2.5)
    assert cell["difference_orientation"] == "positive_favors_candidate"


def test_provisional_total_never_drops_below_declared_existing_id_count():
    data = payload()
    data["planning"]["minimum_pilot_pairs"] = 3
    data["planning"]["target_half_widths"] = {"score": 100.0}
    report = load().plan(data)
    assert report["precision"]["request"]["provisional_common_total_pairs"] == 5
    assert report["precision"]["request"]["additional_common_run_ids"] == 0


def test_invalid_cell_and_contract_failures_are_explicit():
    data = payload()
    data["runs"][0]["score"] = None
    report = load().plan(data)
    assert report["completeness"]["invalid_metric_requests"][0]["method"] == "Base"
    mutations = [
        ("independence", "unknown", "explicitly declared"),
    ]
    for key, value, message in mutations:
        broken = payload()
        broken[key] = value
        with pytest.raises(ValueError, match=message):
            load().plan(broken)
    wrong = payload()
    wrong["planning"]["estimand"] = "group_mean"
    with pytest.raises(ValueError, match="paired_mean_difference"):
        load().plan(wrong)
    assumption = payload()
    assumption["planning"].pop("variance_assumption")
    with pytest.raises(ValueError, match="variance_assumption"):
        load().plan(assumption)


def test_declared_pairing_universe_cannot_hide_observations():
    hidden_id = payload()
    hidden_id["pairing"]["expected_run_ids"] = [0, 1, 2, 3]
    with pytest.raises(ValueError, match="outside expected_run_ids"):
        load().plan(hidden_id)
    hidden_method = payload()
    hidden_method["pairing"]["candidates"] = ["A"]
    with pytest.raises(ValueError, match="outside baseline and candidates"):
        load().plan(hidden_method)
    duplicate = payload()
    duplicate["runs"].append(copy.deepcopy(duplicate["runs"][0]))
    with pytest.raises(ValueError, match="duplicate run id"):
        load().plan(duplicate)
