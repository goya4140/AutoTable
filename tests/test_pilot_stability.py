import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load(name, filename):
    path = ROOT / "skills/paper-table/scripts" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def diagnose(values, target=2.0, cap=30):
    stability = load("pilot_stability_test", "pilot_stability.py")
    planner = load("mean_planner_for_stability_test", "plan_more_data.py")
    return stability.diagnose(
        values,
        list(range(len(values))),
        target,
        0.95,
        cap,
        planner.ci_half_width,
        planner.required_total_runs,
    )


def test_adjusted_fisher_pearson_skewness_matches_reference_definition():
    stability = load("pilot_stability_skew_test", "pilot_stability.py")
    assert stability.adjusted_fisher_pearson_skewness([2, 8, 0, 4, 1, 9, 9, 0]) == pytest.approx(0.3305821804079746)
    assert stability.adjusted_fisher_pearson_skewness([1, 1, 1, 1, 1]) is None


def test_single_variance_creating_run_is_sent_for_review_not_deleted():
    report = diagnose([10.0, 10.0, 10.0, 10.0, 30.0], target=5.0)
    assert report["status"] == "review_required"
    assert report["leave_one_run_out"]["zero_variance_after_omitting_run_ids"] == [4]
    assert "all_observed_variance_depends_on_one_run" in report["review_reasons"]
    assert "do not delete" in report["interpretation"]
    assert report["leave_one_run_out"]["omission_count"] == 5
    assert len(report["leave_one_run_out"]["omission_audit_sha256"]) == 64
    assert "omissions" not in report["leave_one_run_out"]


def test_modified_z_only_labels_potential_extremes_when_mad_is_defined():
    report = diagnose([0.0, 1.0, 2.0, 3.0, 100.0], target=10.0)
    assert report["modified_z_status"] == "computed"
    assert report["potential_extreme_run_ids"] == [4]
    assert "modified_z_labels_potential_extreme_run" in report["review_reasons"]


def test_small_pilot_is_insufficient_not_automatically_abnormal():
    report = diagnose([1.0, 2.0, 3.0, 4.0])
    assert report["status"] == "insufficient_runs_for_stability_diagnostics"
    assert report["review_reasons"] == ["fewer_than_five_valid_runs"]
    assert "leave_one_run_out" not in report


def test_zero_full_variance_has_one_precise_review_reason():
    report = diagnose([7.0, 7.0, 7.0, 7.0, 7.0])
    assert report["status"] == "review_required"
    assert report["review_reasons"] == ["zero_full_sample_variance"]
