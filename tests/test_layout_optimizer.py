import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SKILL = ROOT / "skills/paper-table/scripts"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def example_spec():
    return json.loads((ROOT / "examples/main-results.json").read_text())


def test_renderer_applies_layout_to_latex_and_html():
    renderer = load("layout_renderer", SKILL / "render_table.py")
    spec = example_spec()
    spec["layout"] = {"font_size": "footnotesize", "column_padding_pt": 3.5, "row_stretch": 0.95}
    latex, html = renderer.render(spec)
    assert "\\footnotesize" in latex
    assert "\\setlength{\\tabcolsep}{3.5pt}" in latex
    assert "\\renewcommand{\\arraystretch}{0.95}" in latex
    assert "font-size:13px" in html


def test_renderer_rejects_unreadable_layout_values():
    renderer = load("layout_renderer_invalid", SKILL / "render_table.py")
    spec = example_spec()
    spec["layout"] = {"font_size": "tiny", "column_padding_pt": 0.2, "row_stretch": 0.5}
    with pytest.raises(ValueError):
        renderer.render(spec)


def test_optimizer_selects_a_measured_fitting_layout(tmp_path):
    optimizer = load("layout_optimizer_fit", SKILL / "optimize_layout.py")
    original = example_spec()
    report = optimizer.optimize(original, tmp_path, target_width_pt=469, compile_artifact=False)
    selected = json.loads((tmp_path / "selected-spec.json").read_text())
    chosen = next(row for row in report["candidates"] if row["id"] == report["selected_candidate"])
    assert report["status"] == "selected"
    assert chosen["fits"] and chosen["width_pt"] <= 469.25
    assert selected["rows"] == original["rows"]
    assert selected["columns"] == original["columns"]
    assert (tmp_path / "table.tex").exists() and (tmp_path / "table.html").exists()


def test_optimizer_requests_structural_redesign_instead_of_silent_scaling(tmp_path):
    optimizer = load("layout_optimizer_overflow", SKILL / "optimize_layout.py")
    spec=example_spec()
    spec["columns"]=spec["columns"][:2]
    for row in spec["rows"]: row.pop("f1",None)
    report = optimizer.optimize(spec, tmp_path, target_width_pt=80, compile_artifact=False)
    assert report["status"] == "needs_structural_redesign"
    assert not report["selected_fits"]
    advice = " ".join(report["recommendations"]).lower()
    assert "split" in advice
    assert "do not silently resize" in advice
    assert "resizebox" not in (tmp_path / "table.tex").read_text()


def test_optimizer_splits_only_along_metric_group_boundaries(tmp_path):
    optimizer = load("layout_optimizer_panels", SKILL / "optimize_layout.py")
    contract_eval=load("layout_panel_contract",ROOT/"benchmarks/paperbench/contract_eval.py")
    case_dir=ROOT/"benchmarks/paperbench/cases/neurips24-rankup-utkface"
    spec=json.loads((case_dir/"x.json").read_text())
    report=optimizer.optimize(spec,tmp_path,target_width_pt=350,compile_artifact=False)
    selected=json.loads((tmp_path/"selected-spec.json").read_text())
    assert report["status"]=="selected" and report["structural_transform"]=="panels"
    assert report["panel_count"]==2
    groups={column["key"]:column.get("group") for column in spec["columns"] if column.get("kind")=="metric"}
    for panel in selected["layout"]["panels"]:
        assert len({groups[key] for key in panel["metric_keys"]})==1
    assert [key for panel in selected["layout"]["panels"] for key in panel["metric_keys"]]==[column["key"] for column in spec["columns"] if column.get("kind")=="metric"]
    assert (tmp_path/"table.tex").read_text().count("\\begin{tabular}")==2
    assert (tmp_path/"table.html").read_text().count("<table>")==2
    contract=contract_eval.evaluate(spec,selected,json.loads((case_dir/"case.json").read_text()))
    assert contract["passed_scientific_gate"] and contract["passed_full_contract"]


def test_optimizer_rejects_fragmented_four_panel_page(tmp_path):
    optimizer=load("layout_optimizer_four_panel",SKILL/"optimize_layout.py")
    spec=json.loads((ROOT/"benchmarks/paperbench/cases/neurips24-rankup-utkface/x.json").read_text())
    report=optimizer.optimize(spec,tmp_path,target_width_pt=240,target_height_pt=500,compile_artifact=False)
    assert report["status"]=="needs_structural_redesign"
    assert not report["selected_fits"]
    assert max(candidate["panel_count"] for candidate in report["candidates"])==3


def test_panelized_render_has_exact_numeric_multiset():
    renderer=load("layout_panel_renderer",SKILL/"render_table.py")
    evaluator=load("layout_panel_evaluator",ROOT/"benchmarks/paperbench/evaluate.py")
    spec={
        "caption":"Panels","columns":[
            {"key":"method","label":"Method","kind":"text"},
            {"key":"a","label":"A","kind":"metric","direction":"max","precision":1},
            {"key":"b","label":"B","kind":"metric","direction":"max","precision":1}],
        "rows":[{"method":"Baseline [3]","a":1.0,"b":2.0}],
        "layout":{"font_size":"small","column_padding_pt":5,"row_stretch":1,"panels":[
            {"label":"(a) A","metric_keys":["a"]},{"label":"(b) B","metric_keys":["b"]}]}}
    latex,_=renderer.render(spec)
    recall,precision,hall=evaluator.multiset_recall(evaluator.expected_body_numbers(spec),evaluator.rendered_body_numbers(latex))
    assert (recall,precision,hall)==(1.0,1.0,0)
