#!/usr/bin/env python3
"""Search readable table layouts using real XeLaTeX box measurements."""
from __future__ import annotations

import argparse
import copy
import importlib.util
import itertools
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RENDERER_PATH = HERE / "render_table.py"
ADVISOR_PATH = HERE / "design_advisor.py"
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
STRUCTURAL_CANDIDATE_IDS={"small-standard","small-compact","footnote-comfortable","footnote-compact","footnote-tight"}
WRAP_BASE_IDS={"small-compact","footnote-comfortable","footnote-compact","footnote-tight"}
MAX_AUTOMATIC_PANELS=3


def load_renderer():
    spec = importlib.util.spec_from_file_location("paper_table_layout_renderer", RENDERER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_advisor():
    spec = importlib.util.spec_from_file_location("paper_table_design_advisor", ADVISOR_PATH)
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


def panel_partitions(spec, panel_count=2):
    metrics=[column for column in spec.get("columns",[]) if column.get("kind")=="metric"]
    if len(metrics)<panel_count: return []
    runs=[]
    for column in metrics:
        group=column.get("group")
        if not runs or runs[-1][0]!=group: runs.append([group,[]])
        runs[-1][1].append(column)
    partitions=[]
    if all(group for group,_ in runs) and len(runs)>=panel_count:
        # Keep every semantic group intact, but allow a panel to contain
        # several adjacent complete groups. This is essential for matrices
        # such as one Progress/Success pair per task: one panel per task would
        # be needlessly fragmented, while splitting a pair would be ambiguous.
        for boundaries in itertools.combinations(range(1,len(runs)),panel_count-1):
            chunks=[]
            starts=(0,*boundaries); ends=(*boundaries,len(runs))
            for start,end in zip(starts,ends):
                selected=runs[start:end]
                keys=[column["key"] for _group,columns in selected for column in columns]
                names=[group for group,_columns in selected]
                label=names[0] if len(names)==1 else f"{names[0]} - {names[-1]}"
                chunks.append((label,keys))
            partitions.append((f"whole-groups-{'-'.join(map(str,boundaries))}",chunks))
    elif all(group for group,_ in runs):
        def allocations(remaining,index,current):
            if index==len(runs):
                if remaining==0: yield current
                return
            capacity=len(runs[index][1]); groups_left=len(runs)-index-1
            for count in range(1,min(capacity,remaining-groups_left)+1):
                yield from allocations(remaining-count,index+1,[*current,count])
        for allocation in allocations(panel_count,0,[]):
            chunks=[]
            for (group,columns),count in zip(runs,allocation):
                base,remainder=divmod(len(columns),count); offset=0
                for part in range(count):
                    size=base+(1 if part<remainder else 0); chunk=columns[offset:offset+size]; offset+=size
                    label=group if count==1 else f"{group} ({part+1}/{count})"
                    chunks.append((label,[column["key"] for column in chunk]))
            partitions.append((f"group-splitting-{'-'.join(map(str,allocation))}",chunks))
    else:
        base,remainder=divmod(len(metrics),panel_count); chunks=[]; offset=0
        for index in range(panel_count):
            size=base+(1 if index<remainder else 0); chunk=metrics[offset:offset+size]; offset+=size
            label=" / ".join(column.get("label", column["key"]) for column in chunk)
            chunks.append((label,[column["key"] for column in chunk]))
        partitions.append((f"balanced-{panel_count}",chunks))
    unique=[]; seen=set()
    for partition_id,chunks in partitions:
        signature=tuple(tuple(keys) for _,keys in chunks)
        if signature in seen: continue
        seen.add(signature)
        panels=[{"label":f"({chr(97+index)}) {label}","metric_keys":keys} for index,(label,keys) in enumerate(chunks)]
        unique.append({"id":partition_id,"panels":panels})
    return unique


def measure_panel_candidate(spec, renderer, partition, candidate, target_width, target_height):
    trial=copy.deepcopy(spec)
    trial["layout"]={key:value for key,value in candidate.items() if key!="id"}
    trial["layout"]["panels"]=copy.deepcopy(partition["panels"])
    dimensions=[measure(child,renderer) for _,child in renderer.projected_panels(trial)]
    width=max(item[0] for item in dimensions)
    height=sum(item[1] for item in dimensions)+18*len(dimensions)
    fits=width<=target_width+.25 and height<=target_height+.25
    score=candidate_score(candidate,width,target_width)-.04*(len(dimensions)-1)-(.03 if candidate.get("text_column_width_pt") else 0)
    return {
        **candidate,"id":f"{partition['id']}__{candidate['id']}","panels":partition["panels"],
        "structural_transform":"panels","panel_count":len(dimensions),
        "width_pt":round(width,3),"tabular_height_pt":round(height,3),
        "width_utilization":round(width/target_width,4),"fits":fits,
        "readability_proxy_score":round(score,4),
    }


def recommendations(selected, fits, target_width, width):
    if not fits:
        return [
            f"The narrowest tested layout is {width-target_width:.1f} pt wider than the {target_width:g} pt target.",
            "Split columns by metric family or dataset, keeping the row identity column in each panel.",
            "Shorten repeated headers or move units/directions into grouped headers and notes.",
            "Use a full-width table before considering scriptsize or whole-table scaling.",
            "Do not silently resize the table: scaling would reduce legibility and conceal the structural problem.",
        ]
    messages=[]
    if selected.get("structural_transform")=="panels":
        messages.append(f"Split the metrics into {selected['panel_count']} panels because no readable single-panel candidate fit the target width.")
        messages.append("Repeat the identity columns in every panel and preserve each metric exactly once.")
    if selected.get("text_column_width_pt"):
        messages.append(f"Wrap text identity columns at {selected['text_column_width_pt']:g} pt without abbreviating their content.")
    messages.append(f"Selected {selected['font_size']} text with {selected['column_padding_pt']:g} pt column padding and {selected['row_stretch']:g} row stretch.")
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


def optimize(spec, out_dir, target_width_pt=469.0, target_height_pt=500.0, latexmk="latexmk", compile_artifact=True, case=None):
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
            **candidate,"structural_transform":"none","panel_count":1,"width_pt": round(width, 3), "tabular_height_pt": round(height, 3),
            "width_utilization": round(width / target_width_pt, 4), "fits": fits,
            "readability_proxy_score": round(candidate_score(candidate, width, target_width_pt), 4),
        })
    fitting = [result for result in results if result["fits"]]
    if not fitting:
        structural_typography=[candidate for candidate in CANDIDATES if candidate["id"] in STRUCTURAL_CANDIDATE_IDS]
        last_partitions=[]
        # More than three stacked panels is normally a page-design problem,
        # not a typography success. Stop and advise the author instead of
        # accepting a fragmented full-page table merely because it compiles.
        for panel_count in range(2,MAX_AUTOMATIC_PANELS+1):
            partitions=panel_partitions(spec,panel_count)
            if not partitions: continue
            partitions=sorted(partitions,key=lambda partition:(max(len(panel["metric_keys"]) for panel in partition["panels"]),max(len(panel["metric_keys"]) for panel in partition["panels"])-min(len(panel["metric_keys"]) for panel in partition["panels"]),partition["id"]))[:1]
            last_partitions=partitions
            for partition in partitions:
                for candidate in structural_typography:
                    results.append(measure_panel_candidate(spec,renderer,partition,candidate,target_width_pt,target_height_pt))
            fitting=[result for result in results if result["fits"]]
            if fitting: break
        if not fitting and last_partitions:
            wrapped=[]
            for candidate in CANDIDATES:
                if candidate["id"] not in WRAP_BASE_IDS: continue
                for width in (80.0,65.0):
                    wrapped.append({**candidate,"id":f"{candidate['id']}__wrap-{width:g}","text_column_width_pt":width})
            for partition in last_partitions:
                for candidate in wrapped:
                    results.append(measure_panel_candidate(spec,renderer,partition,candidate,target_width_pt,target_height_pt))
            fitting=[result for result in results if result["fits"]]
    selected = max(fitting, key=lambda result: result["readability_proxy_score"]) if fitting else min(results, key=lambda result: (max(0, result["width_pt"]-target_width_pt), -result["readability_proxy_score"]))
    selected_spec = copy.deepcopy(spec)
    selected_spec["layout"] = {key: selected[key] for key in ("font_size", "column_padding_pt", "row_stretch")}
    if selected.get("text_column_width_pt"): selected_spec["layout"]["text_column_width_pt"]=selected["text_column_width_pt"]
    if selected.get("panels"): selected_spec["layout"]["panels"]=copy.deepcopy(selected["panels"])
    latex, html = renderer.render(selected_spec)
    (out_dir / "selected-spec.json").write_text(json.dumps(selected_spec, indent=2, ensure_ascii=False) + "\n")
    (out_dir / "table.tex").write_text(latex)
    (out_dir / "table.html").write_text(html)
    visual_strategy = load_advisor().advise(selected_spec, case, target_width_pt)
    (out_dir / "design-advice.json").write_text(json.dumps(visual_strategy, indent=2, ensure_ascii=False) + "\n")
    report = {
        "status": "selected" if fitting else "needs_structural_redesign",
        "target_width_pt": target_width_pt, "target_tabular_height_pt": target_height_pt,
        "selected_candidate": selected["id"], "selected_fits": selected["fits"],
        "structural_transform": selected["structural_transform"], "panel_count": selected["panel_count"],
        "selection_policy": "Among physically fitting candidates, maximize a declared proxy favoring readable font size, column padding, row spacing, and width utilization; this is not a human aesthetic score.",
        "visual_strategy": visual_strategy,
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
    parser.add_argument("--target-height-pt", type=float, default=500.0, help="maximum tabular-body height; reserves page space for caption and notes")
    parser.add_argument("--latexmk", default="latexmk")
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    target_width = args.target_width_pt
    case = json.loads(args.case.read_text()) if args.case else None
    if target_width is None and args.case:
        target_width = case["semantic_contract"]["rendering_constraints"]["max_width_pt"]
    report = optimize(spec, args.out_dir, target_width or 469.0, args.target_height_pt, args.latexmk, compile_artifact=not args.no_preview, case=case)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(0 if report["status"] == "selected" else 2)


if __name__ == "__main__":
    main()
