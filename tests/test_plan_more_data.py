import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load():
    path = ROOT / "skills/paper-table/scripts/plan_more_data.py"
    spec = importlib.util.spec_from_file_location("plan_more_data_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload():
    runs = [
        {"method": "A", "run": 0, "score": 10.0},
        {"method": "A", "run": 1, "score": 12.0},
        {"method": "A", "run": 2, "score": 8.0},
        {"method": "A", "run": 3, "score": 10.0},
        {"method": "B", "run": 0, "score": 20.0},
        {"method": "B", "run": 1, "score": 21.0},
        {"method": "B", "run": 2, "score": 19.0},
    ]
    return {
        "schema_version": "paper-table-more-data-plan-v1",
        "group_keys": [{"key": "method"}],
        "metrics": [{"key": "score", "direction": "max", "unit": "points"}],
        "runs": runs,
        "run_id_key": "run",
        "repeat_unit": "independent training seed",
        "independence": "independent",
        "pairing": {
            "mode": "fixed_across_groups",
            "expected_groups": [{"method": "A"}, {"method": "B"}],
            "expected_run_ids": [0, 1, 2, 3],
        },
        "planning": {
            "estimand": "group_mean",
            "confidence_level": 0.95,
            "target_half_widths": {"score": 1.0},
            "minimum_pilot_runs": 4,
            "maximum_total_runs": 30,
            "variance_assumption": "pilot_sd_stable_for_planning_only",
            "interval_assumption": "t_interval_appropriate_for_repeat_distribution",
        },
    }


def test_student_t_quantiles_match_reference_values():
    planner = load()
    assert planner.student_t_quantile(0.975, 2) == pytest.approx(4.30265273, rel=1e-8)
    assert planner.student_t_quantile(0.975, 4) == pytest.approx(2.77644511, rel=1e-8)
    assert planner.student_t_quantile(0.975, 9) == pytest.approx(2.26215716, rel=1e-8)


def test_missing_pair_is_requested_before_provisional_precision_runs():
    report = load().plan(payload())
    assert report["completeness"]["repair_count"] == 1
    assert report["completeness"]["repair_requests"] == [{
        "group": {"method": "B"},
        "run_id": 3,
        "request": "complete_existing_paired_run",
        "metrics": ["score"],
    }]
    assert report["completeness"]["requires_replan_after_repair"]
    cells = {cell["group"]["method"]: cell for cell in report["precision"]["cells"]}
    assert cells["A"]["sample_sd"] == pytest.approx(1.632993161855452)
    assert cells["A"]["current_ci_half_width"] == pytest.approx(2.598456527250219)
    assert cells["A"]["required_total_runs"] == 13
    assert cells["B"]["status"] == "collect_minimum_pilot_then_replan"
    assert report["precision"]["request"]["provisional_common_total_runs"] == 13
    assert report["precision"]["request"]["additional_common_run_ids"] == 9
    assert report["questions_for_author"]


def test_zero_pilot_variance_never_claims_the_target_is_met():
    data = payload()
    data["runs"].append({"method": "B", "run": 3, "score": 20.0})
    for row in data["runs"]:
        if row["method"] == "B":
            row["score"] = 20.0
    report = load().plan(data)
    cell = next(cell for cell in report["precision"]["cells"] if cell["group"] == {"method": "B"})
    assert cell["sample_sd"] == 0
    assert cell["status"] == "zero_pilot_variance_requires_review"
    assert cell["required_total_runs"] is None
    assert not cell["target_met"]
    assert report["precision"]["unresolved_cells"] == 1


def test_invalid_metric_cell_becomes_an_explicit_recovery_request():
    data = payload()
    data["runs"][0]["score"] = None
    report = load().plan(data)
    assert report["completeness"]["invalid_metric_requests"] == [{
        "group": {"method": "A"},
        "run_id": 0,
        "metric": "score",
        "request": "rerun_or_recover_missing_metric",
    }]


def test_duplicate_ids_unknown_independence_and_undeclared_variance_fail():
    duplicate = payload()
    duplicate["runs"].append(dict(duplicate["runs"][0]))
    with pytest.raises(ValueError, match="duplicate run id"):
        load().plan(duplicate)
    dependent = payload()
    dependent["independence"] = "unknown"
    with pytest.raises(ValueError, match="explicitly declared"):
        load().plan(dependent)
    assumption = payload()
    assumption["planning"].pop("variance_assumption")
    with pytest.raises(ValueError, match="variance_assumption"):
        load().plan(assumption)
    interval = payload()
    interval["planning"].pop("interval_assumption")
    with pytest.raises(ValueError, match="interval_assumption"):
        load().plan(interval)
    estimand = payload()
    estimand["planning"]["estimand"] = "paired_difference"
    with pytest.raises(ValueError, match="estimand must be group_mean"):
        load().plan(estimand)


def test_declared_grid_cannot_hide_observed_runs_or_groups():
    run_ids = payload()
    run_ids["pairing"]["expected_run_ids"] = [0, 1, 2]
    with pytest.raises(ValueError, match="outside expected_run_ids"):
        load().plan(run_ids)
    groups = payload()
    groups["pairing"]["expected_groups"] = [{"method": "A"}]
    with pytest.raises(ValueError, match="outside expected_groups"):
        load().plan(groups)
