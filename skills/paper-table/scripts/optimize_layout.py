#!/usr/bin/env python3
"""Search readable table layouts using real XeLaTeX box measurements."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDERER_PATH = HERE / "render_table.py"
FONT_QUALITY = {"small": 1.0, "footnotesize": 0.86, "scriptsize": 0.68}
CANDIDATES = [
    {"id": "small-comfortable", "font_size": "small", "column_padding_pt": 6.0, "row_stretch": 1.08},
    {"id": "small-standard", "font_size": "small", "column_padding_pt": 5.0, "row_stretch": 1.0},
    {"id": "small-compact", "font_size": "small", "column_padding_pt": 3.5, "row_stretch": 0.95},
    {"id": "small-tight", "font_size": "small", "column_padding_pt": 2.0, "row_stretch": 0.9},
    {"id": "footnote-comfortable", "font_size": "footnotesize", "column_padding_pt": 5.0, "row_stretch": 1.05},
    {"id": "footnote-compact", "font_size": "footnotesize", "column_padding_pt": 3.5, "row_stretch": 0.95},
    {"id": "footnote-tight", "font_size": "footnotesize", "column_padding_pt": 2.0, "row_stretch": 0.9},
    {"id": "script-compact", "font_size": "scriptsize", "column_padding_pt": 3.0, "row_stretch": 0.92},
    {"id": "script-tight", "font_size": "scriptsize", "column_padding_pt": 1.5, "row_stretch": 0.85},
]


def load_renderer():
    spec = importlib.util.spec_from_file_location("paper_table_layout_renderer", RENDERER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measurement_source(spec, renderer):
    commands = "\n".join(renderer.layout_commands(spec))
    tabular = renderer.latex_tabular(spec)
    return rf"""\documentclass{{article}}
\usepackage{{booktabs}}
\usepackage{{fontspec}}
\newsavebox{{\papertablebox}}
\begin{{document}}
\savebox{{\papertablebox}}{{\begingroup
{commands}
{tabular}\endgroup}}
\typeout{{PAPERTABLE_WIDTH=\the\wd\papertablebox}}
\typeout{{PAPERTABLE_HEIGHT=\the\dimexpr\ht\papertablebox+\dp\papertablebox\relax}}
\end{{document}}
"""


def measure(spec, renderer):
    with tempfile.TemporaryDirectory(prefix="papertable-measure-") as raw:
        work = Path(raw)
        (work / "measure.tex").write_text(measurement_source(spec, renderer))
        xelatex = shutil.which("xelatex")
        if not xelatex:
            raise RuntimeError("xelatex is required for physical layout measurement")
        completed = subprocess.run(
            [xelatex, "-interaction=nonstopmode", "-halt-on-error", "measure.tex"],
            cwd=work, capture_output=True, text=True,
        )
        if completed.returncode != 0:
            tail = "\n".join((completed.stdout + completed.stderr).splitlines()[-20:])
            raise RuntimeError(f"XeLaTeX measurement failed:\n{tail}")
        log = (work / "measure.log").read_text(errors="replace")
        width = re.search(r"PAPERTABLE_WIDTH=([0-9.]+)pt", log)
        height = re.search(r"PAPERTABLE_HEIGHT=([0-9.]+)pt", log)
        if not width or not height:
            raise RuntimeError("XeLaTeX log did not contain table dimensions")
        return float(width.group(1)), float(height.group(1))


def candidate_score(candidate, width, target_width):
    padding_quality = max(0.0, min(1.0, (candidate["column_padding_pt"] - 1.5) / 4.5))
    row_quality = max(0.0, 1.0 - abs(candidate["row_stretch"] - 1.05) / 0.25)
    utilization = min(1.0, width / target_width)
    return 0.55 * FONT_QUALITY[candidate["font_size"]] + 0.25 * padding_quality + 0.15 * row_quality + 0.05 * utilization


def recommendations(selected, fits, target_width, width):
    if not fits:
        return [
            f"The narrowest tested layout is {width-target_width:.1f} pt wider than the {target_width:g} pt target.",
            "Split columns by metric family or dataset, keeping the row identity column in each panel.",
            "Shorten repeated headers or move units/directions into grouped headers and notes.",
            "Use a full-width table before considering scriptsize or whole-table scaling.",
            "Do not silently resize the table: scaling would reduce legibility and conceal the structural problem.",
        ]
    messages = [f"Selected {selected['font_size']} text with {selected['column_padding_pt']:g} pt column padding and {selected['row_stretch']:g} row stretch."]
    if selected["font_size"] != "small":
        messages.append("The table needs a smaller font at this width; consider splitting metric families if body-text-sized labels are required.")
    if selected["column_padding_pt"] < 3.5:
        messages.append("Column spacing is tight; a structural split would improve scanability if the venue permits additional table space.")
    return messages


def autocrop_png(path):
    try:
        from PIL import Image, ImageChops
        image = Image.open(path).convert("RGB")
        diff = ImageChops.difference(image, Image.new("RGB", image.size, "white"))
        box = diff.getbbox()
        if box:
            margin = 12
            image.crop((max(0, box[0]-margin), max(0, box[1]-margin), min(image.width, box[2]+margin), min(image.height, box[3]+margin))).save(path)
    except ImportError:
        pass


def compile_preview(out_dir, latexmk="latexmk"):
    source = r"""\documentclass{article}
\usepackage[margin=0.5in]{geometry}
\usepackage{booktabs}
\usepackage{fontspec}
\pagestyle{empty}
\begin{document}
\input{table.tex}
\end{document}
"""
    with tempfile.TemporaryDirectory(prefix="papertable-preview-") as raw:
        work = Path(raw)
        (work / "preview.tex").write_text(source)
        shutil.copy2(out_dir / "table.tex", work / "table.tex")
        completed = subprocess.run([latexmk, "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "preview.tex"], cwd=work, capture_output=True, text=True)
        if completed.returncode != 0:
            raise RuntimeError("selected layout failed preview compilation")
        shutil.copy2(work / "preview.pdf", out_dir / "preview.pdf")
        pdftoppm = shutil.which("pdftoppm")
        if pdftoppm:
            subprocess.run([pdftoppm, "-png", "-r", "180", "-singlefile", "preview.pdf", "preview-render"], cwd=work, check=True, capture_output=True)
            generated = work / "preview-render.png"
            if generated.exists(): shutil.copy2(generated, out_dir / "preview.png")
            if (out_dir / "preview.png").exists(): autocrop_png(out_dir / "preview.png")


def optimize(spec, out_dir, target_width_pt=469.0, target_height_pt=620.0, latexmk="latexmk", compile_artifact=True):
    if target_width_pt <= 0 or target_height_pt <= 0:
        raise ValueError("target width and height must be positive")
    renderer = load_renderer()
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for candidate in CANDIDATES:
        trial = copy.deepcopy(spec)
        trial["layout"] = {key: value for key, value in candidate.items() if key != "id"}
        width, height = measure(trial, renderer)
        fits = width <= target_width_pt + 0.25 and height <= target_height_pt + 0.25
        results.append({
            **candidate, "width_pt": round(width, 3), "tabular_height_pt": round(height, 3),
            "width_utilization": round(width / target_width_pt, 4), "fits": fits,
            "readability_proxy_score": round(candidate_score(candidate, width, target_width_pt), 4),
        })
    fitting = [result for result in results if result["fits"]]
    selected = max(fitting, key=lambda result: result["readability_proxy_score"]) if fitting else min(results, key=lambda result: (max(0, result["width_pt"]-target_width_pt), -result["readability_proxy_score"]))
    selected_spec = copy.deepcopy(spec)
    selected_spec["layout"] = {key: selected[key] for key in ("font_size", "column_padding_pt", "row_stretch")}
    latex, html = renderer.render(selected_spec)
    (out_dir / "selected-spec.json").write_text(json.dumps(selected_spec, indent=2, ensure_ascii=False) + "\n")
    (out_dir / "table.tex").write_text(latex)
    (out_dir / "table.html").write_text(html)
    report = {
        "status": "selected" if fitting else "needs_structural_redesign",
        "target_width_pt": target_width_pt, "target_tabular_height_pt": target_height_pt,
        "selected_candidate": selected["id"], "selected_fits": selected["fits"],
        "selection_policy": "Among physically fitting candidates, maximize a declared proxy favoring readable font size, column padding, row spacing, and width utilization; this is not a human aesthetic score.",
        "candidates": results,
        "recommendations": recommendations(selected, bool(fitting), target_width_pt, selected["width_pt"]),
    }
    (out_dir / "layout-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    if compile_artifact:
        compile_preview(out_dir, latexmk)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--case", type=Path, help="PaperBench case.json supplying max_width_pt")
    parser.add_argument("--target-width-pt", type=float)
    parser.add_argument("--target-height-pt", type=float, default=620.0)
    parser.add_argument("--latexmk", default="latexmk")
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    target_width = args.target_width_pt
    if target_width is None and args.case:
        case = json.loads(args.case.read_text())
        target_width = case["semantic_contract"]["rendering_constraints"]["max_width_pt"]
    report = optimize(spec, args.out_dir, target_width or 469.0, args.target_height_pt, args.latexmk, compile_artifact=not args.no_preview)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["status"] == "selected" else 2)


if __name__ == "__main__":
    main()
