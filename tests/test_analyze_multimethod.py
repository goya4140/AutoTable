import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load():
    path = ROOT / "skills/paper-table/scripts/analyze_multimethod.py"
    spec = importlib.util.spec_from_file_location("analyze_multimethod_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload(blocks=6):
    records = []
    for block in range(blocks):
        records.extend([
            {"method": "A", "dataset": block, "score": 0.0},
            {"method": "B", "dataset": block, "score": 1.0},
            {"method": "C", "dataset": block, "score": 2.0},
        ])
    return {
        "schema_version": "paper-table-multimethod-inference-v1",
        "method_key": "method",
        "block_key": "dataset",
        "score_key": "score",
        "methods": ["A", "B", "C"],
        "direction": "max",
        "records": records,
        "design": {
            "blocks": "complete",
            "block_independence": "independent",
            "block_description": "independently sampled datasets",
            "block_independence_evidence": "Each controlled dataset is generated independently.",
        },
        "omnibus": {
            "name": "friedman_block_permutation",
            "rank_tie_policy": "average",
            "exchangeability": "method_labels_exchangeable_within_blocks_under_global_null",
            "exchangeability_rationale": "Under the controlled global null, method labels are arbitrary within every complete dataset block.",
            "alpha": 0.1,
            "exact_max_configurations": 100000,
            "monte_carlo_samples": 9999,
            "seed": 23,
        },
        "posthoc": {
            "baseline": "A",
            "candidates": ["B", "C"],
            "baseline_selection_timing": "predeclared_before_outcome_inspection",
            "gatekeeping": "require_omnibus_rejection",
            "test": "paired_sign_flip_mean",
            "alternative": "two-sided",
            "exchangeability": "paired_signs_exchangeable_under_null",
            "exchangeability_rationale": "Under each pairwise null, complete dataset differences are sign-exchangeable.",
            "exact_max_pairs": 18,
            "monte_carlo_samples": 9999,
            "seed": 29,
            "confidence_interval": {
                "name": "paired_percentile_bootstrap_mean",
                "confidence_level": 0.95,
                "resamples": 1000,
                "seed": 31,
            },
            "multiplicity": {"family_id": "a-versus-all", "correction": "holm", "alpha": 0.1},
        },
    }


def test_exact_friedman_permutation_and_gated_holm_family_are_auditable():
    report = load().analyze(payload())
    assert report["schema_version"] == "paper-table-multimethod-inference-report-v1"
    assert report["omnibus"]["statistic"] == 12.0
    assert report["omnibus"]["pvalue_mode"] == "exact"
    assert report["omnibus"]["total_label_configurations"] == 6 ** 6
    assert report["omnibus"]["evaluated_permutations_or_samples"] == 6 ** 6
    assert report["omnibus"]["p_value"] == pytest.approx(6 / (6 ** 6))
    assert report["omnibus"]["reject_global_null"]
    assert report["descriptive"] == [
        {"method": "A", "mean_score": 0.0, "average_rank": 3.0},
        {"method": "B", "mean_score": 1.0, "average_rank": 2.0},
        {"method": "C", "mean_score": 2.0, "average_rank": 1.0},
    ]
    assert all(row["omnibus_gate_passed"] and row["significance_marker_eligible"] for row in report["posthoc"]["results"])
    assert all(row["reject_null"] for row in report["posthoc"]["results"])


def test_ties_use_average_ranks_and_reduce_unique_label_configurations():
    data = payload(3)
    for row in data["records"]:
        if row["dataset"] == 0 and row["method"] == "C":
            row["score"] = 1.0
    report = load().analyze(data)
    assert report["omnibus"]["blocks_with_ties"] == 1
    assert report["omnibus"]["total_label_configurations"] == 3 * 6 * 6
    ranks = {row["method"]: row["average_rank"] for row in report["descriptive"]}
    assert ranks["B"] == pytest.approx((1.5 + 2 + 2) / 3)
    assert ranks["C"] == pytest.approx((1.5 + 1 + 1) / 3)


def test_monte_carlo_omnibus_is_deterministic_and_never_zero():
    data = payload()
    data["omnibus"]["exact_max_configurations"] = 1
    first = load().analyze(data)
    second = load().analyze(data)
    assert first == second
    assert first["omnibus"]["pvalue_mode"] == "monte_carlo_plus_one"
    assert 0 < first["omnibus"]["p_value"] <= 1


def test_global_null_closes_the_significance_marker_gate():
    data = payload()
    for row in data["records"]:
        row["score"] = 1.0
    report = load().analyze(data)
    assert report["omnibus"]["statistic"] == 0.0
    assert report["omnibus"]["p_value"] == 1.0
    assert not report["omnibus"]["reject_global_null"]
    for result in report["posthoc"]["results"]:
        assert result["p_adjusted"] == 1.0
        assert not result["omnibus_gate_passed"]
        assert not result["reject_null"]
        assert not result["significance_marker_eligible"]


def test_incomplete_blocks_and_posthoc_selection_are_rejected():
    incomplete = payload()
    incomplete["records"].pop()
    with pytest.raises(ValueError, match="incomplete"):
        load().analyze(incomplete)
    cherry_picked = payload()
    cherry_picked["posthoc"]["candidates"] = ["C"]
    with pytest.raises(ValueError, match="every other method"):
        load().analyze(cherry_picked)
    late_baseline = payload()
    late_baseline["posthoc"]["baseline_selection_timing"] = "chosen_after_results"
    with pytest.raises(ValueError, match="predeclared"):
        load().analyze(late_baseline)


def test_omnibus_gate_cannot_be_disabled():
    data = payload()
    data["posthoc"]["gatekeeping"] = "none"
    with pytest.raises(ValueError, match="require omnibus rejection"):
        load().analyze(data)
