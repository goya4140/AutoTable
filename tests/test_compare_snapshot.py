import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load():
    path = ROOT / "skills/paper-table/scripts/compare_snapshot.py"
    spec = importlib.util.spec_from_file_location("compare_snapshot_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def specs():
    published = {
        "columns": [
            {"key": "method", "label": "Method", "kind": "text"},
            {"key": "score", "label": "Score", "kind": "metric", "direction": "max", "unit": "%", "precision": 2},
        ],
        "rows": [{"method": "A", "score": 1.234}, {"method": "B", "score": 2.0}],
    }
    current = {
        "columns": [dict(column) for column in published["columns"]],
        "rows": [{"method": "A", "score": 1.2339}, {"method": "B", "score": 2.0}],
    }
    return current, published


def test_comparison_uses_published_display_precision_not_arbitrary_tolerance():
    current, published = specs()
    report = load().compare(current, published, "method")
    assert report["published_exact_gold"]
    current["rows"][0]["score"] = 1.224
    report = load().compare(current, published, "method")
    assert not report["published_exact_gold"]
    assert report["mismatches"][0]["published"] == 1.23
    assert report["mismatches"][0]["snapshot"] == 1.22


def test_direction_drift_blocks_exact_gold_even_when_values_match():
    current, published = specs()
    current["columns"][1]["direction"] = "min"
    report = load().compare(current, published, "method")
    assert not report["published_exact_gold"]
    assert report["structural_mismatches"][0]["path"] == "columns.score.direction"


def test_missing_row_blocks_exact_gold():
    current, published = specs()
    current["rows"].pop()
    report = load().compare(current, published, "method")
    assert not report["published_exact_gold"]
    assert any(item["message"] == "published row missing from reconstruction" for item in report["structural_mismatches"])


def test_mismatch_order_follows_published_row_order():
    current, published = specs()
    current["rows"][0]["score"] = 1.0
    current["rows"][1]["score"] = 3.0
    report = load().compare(current, published, "method")
    assert [item["row"] for item in report["mismatches"]] == ["A", "B"]
