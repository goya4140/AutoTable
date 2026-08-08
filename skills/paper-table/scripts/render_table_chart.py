#!/usr/bin/env python3
"""Render a code-first, exact-value table-chart for one dominant metric."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import tempfile
from pathlib import Path

MPL_CACHE = Path(tempfile.gettempdir()) / "papertable-matplotlib-cache"
MPL_CACHE.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPL_CACHE))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

HERE = Path(__file__).resolve().parent
ADVISOR_PATH = HERE / "design_advisor.py"
INK = "#202124"
MUTED = "#667085"
GRID = "#D9DEE7"
BLUE = "#4C78A8"
BLUE_DARK = "#284B73"
ORANGE = "#D97706"


def load_advisor():
    spec = importlib.util.spec_from_file_location("paper_table_chart_advisor", ADVISOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cell_parts(cell):
    if isinstance(cell, (int, float)) and not isinstance(cell, bool) and math.isfinite(cell):
        return float(cell), None, None
    if not isinstance(cell, dict) or not isinstance(cell.get("mean"), (int, float)):
        raise ValueError("table-chart metric cells must be finite numbers or objects containing mean")
    if cell.get("values") is not None:
        raise ValueError("raw values must be aggregated with an explicit uncertainty statistic before table-chart rendering")
    mean = float(cell["mean"])
    if "sd" in cell:
        return mean, float(cell["sd"]), "SD"
    if "se" in cell:
        return mean, float(cell["se"]), "SE"
    for key, label in (("ci95", "95% CI"), ("ci90", "90% CI")):
        interval = cell.get(key)
        if isinstance(interval, list) and len(interval) == 2:
            return mean, (mean - float(interval[0]), float(interval[1]) - mean), label
    return mean, None, None


def format_number(value, precision, signed=False):
    prefix = "+" if signed and value > 0 else ""
    return f"{prefix}{value:.{precision}f}"


def chart_contract(spec, advice, metric, labels, values, uncertainty_label, output_dir, claim=""):
    return {
        "analytical_question": "How does the reported metric compare across the displayed rows?",
        "takeaway": claim or "No author-supplied takeaway; use the visual for direct comparison only.",
        "family": "Comparison & Ranking",
        "variant": advice["primary_form"],
        "data_sufficiency": {"rows": len(labels), "metric_count": 1, "uncertainty": uncertainty_label},
        "renderer": "matplotlib-static",
        "metric": {key: metric.get(key) for key in ("key", "label", "direction", "unit", "precision")},
        "palette_policy": "hard two-root cap" if advice["primary_form"] == "diverging_table_chart" else "single-root preferred",
        "palette": {"positive_or_primary": ORANGE if advice["primary_form"] == "diverging_table_chart" else BLUE, "negative": BLUE, "ink": INK, "grid": GRID},
        "non_color_distinction": "direct signed value labels and a visible zero reference",
        "rows": [{"label": label, "value": value} for label, value in zip(labels, values)],
        "provenance": spec.get("provenance", {}),
        "exports": [str(output_dir / f"table-chart.{suffix}") for suffix in ("svg", "pdf", "png")],
    }


def render(spec, output_dir, case=None, target_width_pt=None):
    metrics = [column for column in spec.get("columns", []) if column.get("kind") == "metric"]
    texts = [column for column in spec.get("columns", []) if column.get("kind") != "metric"]
    if len(metrics) != 1 or not texts:
        raise ValueError("table-chart rendering requires exactly one metric and at least one text identity column")
    metric = metrics[0]
    if metric.get("direction") not in {"min", "max"} or not metric.get("unit"):
        raise ValueError("table-chart rendering requires a resolved metric direction and unit")
    advisor = load_advisor()
    advice = advisor.advise(spec, case, target_width_pt)
    supplied_claim = advisor.claim_text(spec, case)
    if advice["primary_form"] not in {"diverging_table_chart", "ranked_table_chart"}:
        raise ValueError(f"design advisor recommends {advice['primary_form']}; keep this result as a conventional table")
    identity = texts[0]["key"]
    labels, values, errors, groups = [], [], [], []
    uncertainty_labels = set()
    for row in spec.get("rows", []):
        mean, error, uncertainty = cell_parts(row.get(metric["key"]))
        labels.append(str(row.get(identity, "")))
        values.append(mean)
        errors.append(error)
        groups.append(row.get("group"))
        if uncertainty:
            uncertainty_labels.add(uncertainty)
    if len(labels) < 2 or len(labels) > 16:
        raise ValueError("table-chart rendering supports 2 to 16 comparable rows")
    if len(uncertainty_labels) > 1:
        raise ValueError("mixed uncertainty kinds require separate explanation and cannot share one chart legend")
    precision = int(metric.get("precision", 2))
    signed = advice["primary_form"] == "diverging_table_chart"
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Serif", "svg.fonttype": "none", "pdf.fonttype": 42})
    longest = max(len(label) for label in labels)
    width = min(10.5, max(6.2, 5.6 + longest * 0.045))
    height = max(2.8, 1.55 + 0.47 * len(labels))
    fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)
    y = list(range(len(labels)))
    colors = []
    for label, value, group in zip(labels, values, groups):
        explicit_ours = "ours" in label.lower() or (isinstance(group, str) and "ours" in group.lower())
        if signed:
            colors.append(ORANGE if value >= 0 else BLUE)
        else:
            colors.append(ORANGE if explicit_ours else BLUE)
    bars = ax.barh(y, values, color=colors, edgecolor=[BLUE_DARK if color == BLUE else "#8A4B00" for color in colors], linewidth=0.7, height=0.58)
    if any(error is not None for error in errors):
        lower = [error[0] if isinstance(error, tuple) else error or 0 for error in errors]
        upper = [error[1] if isinstance(error, tuple) else error or 0 for error in errors]
        ax.errorbar(values, y, xerr=[lower, upper], fmt="none", ecolor=INK, elinewidth=0.9, capsize=2.5, capthick=0.9, zorder=3)
    minimum = min([0.0, *values]); maximum = max([0.0, *values]); span = max(maximum - minimum, max(abs(minimum), abs(maximum)) * 0.2, 1.0)
    pad = span * 0.16
    ax.set_xlim(minimum - (pad if minimum < 0 else 0), maximum + pad)
    ax.axvline(0, color=INK, linewidth=1.0, zorder=0)
    ax.set_yticks(y, labels, fontsize=10.5, color=INK)
    ax.invert_yaxis()
    for index, (bar, value, error) in enumerate(zip(bars, values, errors)):
        uncertainty = ""
        if isinstance(error, tuple):
            uncertainty = f" [{value-error[0]:.{precision}f}, {value+error[1]:.{precision}f}]"
        elif error is not None:
            uncertainty = f" ± {error:.{precision}f}"
        label = format_number(value, precision, signed) + uncertainty
        offset = span * 0.025
        x = value + offset if value >= 0 else value - offset
        ax.text(x, index, label, va="center", ha="left" if value >= 0 else "right", fontsize=9.5, fontweight="semibold", color=INK)
    for index in range(1, len(groups)):
        if groups[index] != groups[index - 1] and groups[index] is not None:
            ax.axhline(index - 0.5, color=GRID, linewidth=0.8)
    direction = "higher is better" if metric["direction"] == "max" else "lower is better"
    unit = metric.get("unit")
    unit_text = "" if unit == "dimensionless" else f" ({unit})"
    ax.set_xlabel(f"{metric.get('label', metric['key'])}{unit_text}; {direction}", fontsize=10, color=INK, labelpad=8)
    ax.set_title(spec.get("caption") or f"{metric.get('label', metric['key'])} by {texts[0].get('label', identity)}", loc="left", fontsize=10.5, color=MUTED, pad=10)
    fig.suptitle(spec.get("title") or metric.get("label", metric["key"]), x=0.01, ha="left", fontsize=14, fontweight="bold", color=INK)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.xaxis.grid(True, color=GRID, linewidth=0.65)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", colors=MUTED, labelsize=9)
    ax.tick_params(axis="y", length=0, pad=8)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    description = f"Horizontal {advice['primary_form']} of {metric.get('label', metric['key'])} for {len(labels)} rows, with exact value labels."
    for suffix in ("svg", "pdf", "png"):
        metadata = {"Title": spec.get("title") or metric.get("label", metric["key"]), "Subject": description} if suffix == "pdf" else {"Title": spec.get("title") or metric.get("label", metric["key"]), "Description": description}
        fig.savefig(output_dir / f"table-chart.{suffix}", dpi=220 if suffix == "png" else None, bbox_inches="tight", facecolor="white", metadata=metadata)
    plt.close(fig)
    uncertainty_label = next(iter(uncertainty_labels), None)
    contract = chart_contract(spec, advice, metric, labels, values, uncertainty_label, output_dir, supplied_claim)
    contract["design_advice"] = advice
    (output_dir / "chart-spec.json").write_text(json.dumps(contract, indent=2, ensure_ascii=False) + "\n")
    return contract


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--case", type=Path)
    parser.add_argument("--target-width-pt", type=float)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text())
    case = json.loads(args.case.read_text()) if args.case else None
    print(json.dumps(render(spec, args.out_dir, case, args.target_width_pt), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
