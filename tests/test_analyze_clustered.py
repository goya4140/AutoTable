import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load():
    path = ROOT / "skills/paper-table/scripts/analyze_paired.py"
    spec = importlib.util.spec_from_file_location("analyze_clustered_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload(estimand="equal_cluster_mean"):
    cluster_differences = {
        "study-a": [1.0, 1.0],
        "study-b": [1.0],
        "study-c": [-1.0, -1.0, -1.0],
        "study-d": [1.0],
    }
    records = []
    for cluster, differences in cluster_differences.items():
        for index, difference in enumerate(differences):
            unit = f"{cluster}-task-{index}"
            records.extend([
                {"method": "baseline", "task": unit, "study": cluster, "score": 0.0},
                {"method": "candidate", "task": unit, "study": cluster, "score": difference},
            ])
    return {
        "schema_version": "paper-table-paired-inference-v2",
        "method_key": "method",
        "unit_key": "task",
        "score_key": "score",
        "baseline": "baseline",
        "candidates": ["candidate"],
        "direction": "max",
        "records": records,
        "design": {
            "pairing": "complete",
            "unit_independence": "nested_within_independent_clusters",
            "unit_description": "tasks nested within independently sampled studies",
            "cluster_key": "study",
            "cluster_description": "independently sampled study",
            "cluster_independence": "independent",
            "cluster_independence_evidence": "The four studies were sampled independently; tasks share study-level conditions.",
            "cluster_estimand": estimand,
        },
        "test": {
            "name": "cluster_sign_flip_mean",
            "alternative": "two-sided",
            "exchangeability": "cluster_signs_exchangeable_under_null",
            "exchangeability_rationale": "Under the null, the orientation of each independent study-level aggregate difference is exchangeable.",
            "exact_max_clusters": 18,
            "monte_carlo_samples": 9999,
            "seed": 17,
        },
        "confidence_interval": {
            "name": "cluster_percentile_bootstrap_mean",
            "confidence_level": 0.95,
            "resamples": 1000,
            "seed": 19,
        },
        "multiplicity": {"family_id": "clustered-main", "correction": "none", "alpha": 0.05},
    }


def test_equal_cluster_estimand_randomizes_and_resamples_intact_clusters():
    report = load().analyze(payload())
    result = report["results"][0]
    assert report["schema_version"] == "paper-table-paired-inference-report-v2"
    assert result["mean_improvement"] == 0.5
    assert result["n_pairs"] == 7 and result["n_clusters"] == 4
    assert result["cluster_sizes"] == [2, 1, 3, 1]
    assert result["p_raw"] == 0.625
    assert result["pvalue_mode"] == "exact" and result["permutations_or_samples"] == 16
    assert result["randomization_unit"] == "cluster"
    assert result["bootstrap_resampling_unit"] == "cluster"
    assert len(result["cluster_ids_sha256"]) == 64
    assert report["design"]["cluster_size_summary"] == {"minimum": 1, "maximum": 3, "unequal": True}
    assert report["diagnostics"] == {
        "few_clusters_warning": True,
        "exact_sign_configurations": 16,
        "best_case_two_sided_exact_p_resolution": 0.125,
    }
    assert any("extra resamples do not create independent information" in note for note in report["notes"])


def test_unit_weighted_estimand_is_explicit_and_changes_the_effect_not_the_unit():
    first = load().analyze(payload("unit_weighted_mean"))
    second = load().analyze(payload("unit_weighted_mean"))
    assert first == second
    result = first["results"][0]
    assert result["mean_improvement"] == pytest.approx(1 / 7)
    assert result["p_raw"] == 1.0
    assert result["randomization_unit"] == "cluster"
    assert result["cluster_estimand"] == "unit_weighted_mean"


def test_cluster_assignment_must_be_consistent_across_methods():
    data = payload()
    candidate = next(row for row in data["records"] if row["method"] == "candidate")
    candidate["study"] = "different-study"
    with pytest.raises(ValueError, match="maps to multiple clusters"):
        load().analyze(data)


def test_cluster_independence_and_exchangeability_are_blocking():
    independence = payload()
    independence["design"]["cluster_independence"] = "unknown"
    with pytest.raises(ValueError, match="independent clusters"):
        load().analyze(independence)
    exchangeability = payload()
    exchangeability["test"].pop("exchangeability_rationale")
    with pytest.raises(ValueError, match="cluster-sign exchangeability"):
        load().analyze(exchangeability)


def test_too_few_independent_clusters_are_rejected():
    data = payload()
    data["records"] = [row for row in data["records"] if row["study"] != "study-d"]
    with pytest.raises(ValueError, match="at least four independent clusters"):
        load().analyze(data)
