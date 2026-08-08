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
    report = optimizer.optimize(example_spec(), tmp_path, target_width_pt=80, compile_artifact=False)
    assert report["status"] == "needs_structural_redesign"
    assert not report["selected_fits"]
    advice = " ".join(report["recommendations"]).lower()
    assert "split" in advice
    assert "do not silently resize" in advice
    assert "resizebox" not in (tmp_path / "table.tex").read_text()
