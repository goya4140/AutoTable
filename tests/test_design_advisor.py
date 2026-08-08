import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "skills/paper-table/scripts/design_advisor.py"
CHART_SCRIPT = ROOT / "skills/paper-table/scripts/render_table_chart.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_signed_single_metric_gets_diverging_table_chart():
    advisor = load("advisor_signed", SCRIPT)
    spec = {
        "claim": "The method improves accuracy across emotion transitions.",
        "columns": [
            {"key": "transition", "label": "Transition", "kind": "text"},
            {"key": "gain", "label": "Accuracy gain", "kind": "metric", "direction": "max", "unit": "percentage points"},
        ],
        "rows": [
            {"transition": "Angry–Sad", "gain": -3.0},
            {"transition": "Neutral–Sad", "gain": 2.0},
            {"transition": "Sad–Worried", "gain": 10.4},
        ],
    }
    report = advisor.advise(spec)
    assert report["primary_form"] == "diverging_table_chart"
    assert "zero baseline" in report["proposal"]["hierarchy"]
    assert "+/− signs" in report["proposal"]["color"]


def test_narrow_grouped_result_gets_semantic_panels():
    advisor = load("advisor_panels", SCRIPT)
    case_dir = ROOT / "benchmarks/paperbench/cases/neurips24-rankup-utkface"
    spec = json.loads((case_dir / "x.json").read_text())
    case = json.loads((case_dir / "case.json").read_text())
    report = advisor.advise(spec, case, 350)
    assert report["primary_form"] == "semantic_panel_table"
    assert report["input_facts"]["metric_columns"] == 6
    assert report["input_facts"]["comparison_groups_supplied"]


def test_missing_semantics_disable_unqualified_emphasis(tmp_path):
    spec = {
        "columns": [
            {"key": "method", "label": "Method", "kind": "text"},
            {"key": "score", "label": "Score", "kind": "metric"},
        ],
        "rows": [{"method": "A", "score": 1}, {"method": "B", "score": 2}],
    }
    source = tmp_path / "spec.json"
    source.write_text(json.dumps(spec))
    result = subprocess.run([sys.executable, str(SCRIPT), str(source)], check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    assert {question["field_id"] for question in report["questions"]} >= {"metric_directions", "metric_units"}
    assert any("Do not rank" in warning for warning in report["warnings"])
    assert report["proposal"]["emphasis"].startswith("best/second-best only")


def test_explicit_variant_dimension_gets_ablation_table():
    advisor = load("advisor_ablation", SCRIPT)
    spec = {
        "columns": [
            {"key": "variant", "label": "Variant", "kind": "text"},
            {"key": "acc", "label": "Accuracy", "kind": "metric", "direction": "max", "unit": "%"},
        ],
        "rows": [{"variant": "Base", "acc": 80}, {"variant": "+ module", "acc": 82}],
    }
    assert advisor.advise(spec)["primary_form"] == "ablation_table"


def test_per_run_rows_trigger_aggregation_question():
    advisor = load("advisor_runs", SCRIPT)
    spec = {
        "columns": [
            {"key": "method", "label": "Method", "kind": "text"},
            {"key": "seed", "label": "Seed", "kind": "text"},
            {"key": "score", "label": "Score", "kind": "metric", "direction": "max", "unit": "%"},
        ],
        "rows": [
            {"method": "A", "seed": 0, "score": 80},
            {"method": "A", "seed": 1, "score": 82},
        ],
    }
    report = advisor.advise(spec)
    assert report["input_facts"]["run_identifier_columns"] == ["seed"]
    assert report["questions"][0]["field_id"] == "uncertainty_source"
    assert any("Per-run identifiers" in warning for warning in report["warnings"])


def test_table_chart_exports_editable_exact_value_artifacts(tmp_path):
    renderer = load("table_chart_renderer", CHART_SCRIPT)
    spec = {
        "title": "Accuracy gain by transition",
        "caption": "Accuracy change relative to the frozen baseline.",
        "claim": "The method improves most transitions.",
        "columns": [
            {"key": "transition", "label": "Transition", "kind": "text"},
            {"key": "gain", "label": "Accuracy gain", "kind": "metric", "direction": "max", "unit": "percentage points", "precision": 1},
        ],
        "rows": [
            {"transition": "Angry–Sad", "gain": -3.0},
            {"transition": "Neutral–Sad", "gain": 2.0},
            {"transition": "Sad–Worried", "gain": 10.4},
        ],
    }
    contract = renderer.render(spec, tmp_path)
    assert contract["variant"] == "diverging_table_chart"
    assert [row["value"] for row in contract["rows"]] == [-3.0, 2.0, 10.4]
    for suffix in ("svg", "pdf", "png"):
        assert (tmp_path / f"table-chart.{suffix}").stat().st_size > 1000
    svg = (tmp_path / "table-chart.svg").read_text()
    assert "Angry–Sad" in svg and "+10.4" in svg and "Accuracy gain" in svg


def test_table_chart_refuses_multi_metric_lookup_table(tmp_path):
    import pytest
    renderer = load("table_chart_reject", CHART_SCRIPT)
    spec = json.loads((ROOT / "examples/main-results.json").read_text())
    with pytest.raises(ValueError, match="exactly one metric"):
        renderer.render(spec, tmp_path)


def test_table_chart_refuses_unaggregated_raw_values(tmp_path):
    import pytest
    renderer = load("table_chart_raw_values", CHART_SCRIPT)
    spec = {
        "claim": "Score changes by method.",
        "columns": [
            {"key": "method", "label": "Method", "kind": "text"},
            {"key": "score", "label": "Score change", "kind": "metric", "direction": "max", "unit": "points"},
        ],
        "rows": [
            {"method": "A", "score": {"mean": -1, "values": [-2, 0]}},
            {"method": "B", "score": {"mean": 2, "values": [1, 3]}},
        ],
    }
    with pytest.raises(ValueError, match="must be aggregated"):
        renderer.render(spec, tmp_path)
