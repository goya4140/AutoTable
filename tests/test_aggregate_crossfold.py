import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]


def load():
    path = ROOT / "skills/paper-table/scripts/aggregate_crossfold.py"
    spec = importlib.util.spec_from_file_location("aggregate_crossfold_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def payload():
    records = []
    values = {
        ("d1", 0): {"A": 0.9, "B": 0.8, "C": 0.7},
        ("d1", 1): {"A": 0.8, "B": 0.9, "C": 0.7},
        ("d2", 0): {"A": 0.6, "B": 0.5, "C": 0.4},
        ("d2", 1): {"A": 0.5, "B": 0.6, "C": 0.4},
    }
    for (dataset, fold), methods in values.items():
        for method, score in methods.items():
            records.append({"method": method, "dataset": dataset, "fold": fold, "accuracy": score})
    return {
        "schema_version": "paper-table-crossfold-v1",
        "method_key": "method",
        "dataset_key": "dataset",
        "fold_key": "fold",
        "expected_folds": [0, 1],
        "method_order": ["A", "B", "C"],
        "score": {"key": "accuracy", "label": "Mean accuracy", "direction": "max", "unit": "proportion"},
        "precision": 3,
        "records": records,
    }


def test_complete_grid_produces_rank_z_and_win_statistics():
    out = load().aggregate(payload())
    assert out["grid_audit"] == {
        "methods": 3,
        "datasets": 2,
        "folds_per_dataset": 2,
        "evaluation_units": 4,
        "records": 12,
        "evaluation_units_sha256": out["grid_audit"]["evaluation_units_sha256"],
    }
    rows = {row["method"]: row for row in out["rows"]}
    assert rows["A"]["mean_score"] == 0.7
    assert rows["A"]["mean_rank"] == 1.5
    assert rows["A"]["num_wins"] == 2
    assert rows["C"]["mean_rank"] == 3.0
    assert len(out["aggregation_audit"]) == 18
    directions = {column["key"]: column["direction"] for column in out["columns"] if column.get("kind") == "metric"}
    assert directions["mean_rank"] == "min" and directions["std_z_score"] == "min"


def test_missing_paired_method_fold_is_rejected():
    data = payload()
    data["records"].pop()
    with pytest.raises(ValueError, match="incomplete paired method grid"):
        load().aggregate(data)


def test_duplicate_method_fold_is_rejected():
    data = payload()
    data["records"].append(dict(data["records"][0]))
    with pytest.raises(ValueError, match="duplicate method result"):
        load().aggregate(data)


def test_all_method_tie_rejects_undefined_z_score():
    data = payload()
    for record in data["records"]:
        if record["dataset"] == "d1" and record["fold"] == 0:
            record["accuracy"] = 1.0
    with pytest.raises(ValueError, match="Z-score is undefined"):
        load().aggregate(data)


def test_tied_top_does_not_award_a_strict_win():
    data = payload()
    for record in data["records"]:
        if record["dataset"] == "d1" and record["fold"] == 0 and record["method"] == "B":
            record["accuracy"] = 0.9
    out = load().aggregate(data)
    rows = {row["method"]: row for row in out["rows"]}
    assert rows["A"]["num_wins"] == 1
    assert rows["B"]["num_wins"] == 2
