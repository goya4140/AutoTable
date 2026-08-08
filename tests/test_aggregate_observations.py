import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load_aggregator():
    path = ROOT / "skills/paper-table/scripts/aggregate_observations.py"
    spec = importlib.util.spec_from_file_location("aggregate_observations_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload():
    return {
        "schema_version": "paper-table-observations-v1",
        "group_keys": [{"key": "model", "label": "Model"}],
        "observation_id_key": "example_id",
        "denominators": {"all": ["a", "b", "c"]},
        "metrics": [
            {"key": "accuracy", "label": "Accuracy", "field": "correct", "operation": "rate", "denominator": "all", "scale": 100, "precision": 1, "direction": "max", "unit": "%"},
            {"key": "score", "label": "Score", "field": "score", "operation": "mean", "denominator": "all", "precision": 1, "direction": "max", "unit": "points"},
        ],
        "observations": [
            {"model": "A", "example_id": "a", "correct": True, "score": 1},
            {"model": "A", "example_id": "b", "correct": False, "score": 2},
            {"model": "A", "example_id": "c", "correct": True, "score": 3},
        ],
    }


def test_aggregates_values_and_emits_cell_level_audit():
    result = load_aggregator().aggregate(payload())
    assert result["rows"] == [{"model": "A", "accuracy": 66.7, "score": 2.0}]
    accuracy, score = result["aggregation_audit"]
    assert accuracy["numerator_count"] == 2 and accuracy["n"] == 3
    assert score["sum"] == 6.0 and score["n"] == 3
    assert len(accuracy["observation_ids_sha256"]) == 64


def test_duplicate_observation_ids_are_rejected():
    data = payload()
    data["observations"].append(dict(data["observations"][0]))
    with pytest.raises(ValueError, match="duplicate observation ID"):
        load_aggregator().aggregate(data)
