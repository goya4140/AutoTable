import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load():
    path = ROOT / "skills/paper-table/scripts/analyze_paired.py"
    spec = importlib.util.spec_from_file_location("analyze_paired_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload():
    records = []
    for unit in range(5):
        records.extend([
            {"method": "baseline", "dataset": unit, "score": 0.0},
            {"method": "always_better", "dataset": unit, "score": 1.0},
            {"method": "mixed", "dataset": unit, "score": 1.0 if unit % 2 else -1.0},
        ])
    return {
        "schema_version": "paper-table-paired-inference-v1",
        "method_key": "method",
        "unit_key": "dataset",
        "score_key": "score",
        "baseline": "baseline",
        "candidates": ["always_better", "mixed"],
        "direction": "max",
        "records": records,
        "design": {
            "pairing": "complete",
            "unit_independence": "independent",
            "unit_description": "synthetic independent datasets",
            "unit_independence_evidence": "Each dataset was generated independently.",
        },
        "test": {
            "name": "paired_sign_flip_mean",
            "alternative": "two-sided",
            "exchangeability": "paired_signs_exchangeable_under_null",
            "exchangeability_rationale": "Under the synthetic null, the direction of each paired difference is arbitrary.",
            "exact_max_pairs": 18,
            "monte_carlo_samples": 9999,
            "seed": 7,
        },
        "confidence_interval": {"name": "paired_percentile_bootstrap_mean", "confidence_level": 0.95, "resamples": 1000, "seed": 11},
        "multiplicity": {"family_id": "main", "correction": "holm", "alpha": 0.2},
    }


def test_exact_sign_flip_bootstrap_and_holm_are_auditable():
    report = load().analyze(payload())
    results = {row["method"]: row for row in report["results"]}
    better = results["always_better"]
    assert better["mean_improvement"] == 1.0
    assert better["improvement_ci"] == [1.0, 1.0]
    assert better["p_raw"] == 0.0625
    assert better["p_adjusted"] == 0.125
    assert better["reject_null"]
    assert better["pvalue_mode"] == "exact" and better["permutations_or_samples"] == 32
    assert len(better["paired_unit_ids_sha256"]) == 64
    assert not results["mixed"]["reject_null"]


def test_missing_pair_is_rejected():
    data = payload()
    data["records"] = [row for row in data["records"] if not (row["method"] == "mixed" and row["dataset"] == 4)]
    with pytest.raises(ValueError, match="complete baseline unit set"):
        load().analyze(data)


def test_duplicate_pair_is_rejected():
    data = payload()
    data["records"].append(dict(data["records"][0]))
    with pytest.raises(ValueError, match="duplicate paired unit"):
        load().analyze(data)


def test_independence_must_be_explicit():
    data = payload()
    data["design"]["unit_independence"] = "unknown"
    with pytest.raises(ValueError, match="independent paired units"):
        load().analyze(data)


def test_multiple_comparisons_cannot_skip_correction():
    data = payload()
    data["multiplicity"]["correction"] = "none"
    with pytest.raises(ValueError, match="require Holm correction"):
        load().analyze(data)


def test_monte_carlo_mode_is_deterministic_and_uses_plus_one_pvalue():
    data = payload()
    data["test"]["exact_max_pairs"] = 2
    first = load().analyze(data)
    second = load().analyze(data)
    assert first == second
    result = first["results"][0]
    assert result["pvalue_mode"] == "monte_carlo_plus_one"
    assert 0 < result["p_raw"] <= 1
    assert result["test_seed"] is not None


def test_nested_folds_cannot_be_claimed_as_independent_units():
    data = payload()
    data["design"]["cluster_key"] = "dataset_family"
    for record in data["records"]:
        record["dataset_family"] = record["dataset"] // 2
    with pytest.raises(ValueError, match="nested within clusters"):
        load().analyze(data)


def test_sign_flip_exchangeability_requires_a_rationale():
    data = payload()
    data["test"].pop("exchangeability_rationale")
    with pytest.raises(ValueError, match="exchangeability declaration and rationale"):
        load().analyze(data)
