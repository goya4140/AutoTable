from __future__ import annotations

import html
from typing import Any

from .planner import emphasis_map


def latex_escape(value: Any) -> str:
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}", "±": r"$\pm$",
    }
    return "".join(replacements.get(character, character) for character in str(value))


def _metric_header(meta: dict[str, Any]) -> str:
    arrow = r"$\uparrow$" if meta["direction"] == "max" else r"$\downarrow$"
    unit = f" ({latex_escape(meta['unit'])})" if meta.get("unit") else ""
    return f"{latex_escape(meta['label'])}{unit} {arrow}"


def _formatted_cell(cell: dict[str, Any] | None, precision: int) -> str:
    if cell is None:
        return "--"
    mean = f"{cell['mean']:.{precision}f}"
    if cell["sd"] is None:
        return mean
    return f"{mean} $\\pm$ {cell['sd']:.{precision}f}"


def render_latex(spec: dict[str, Any], caption: str) -> str:
    columns = spec["columns"]
    wide = len(columns) > 4
    environment = "table*" if wide else "table"
    lines = [
        f"\\begin{{{environment}}}[t]",
        "  \\centering",
        "  \\footnotesize" if wide else "  \\small",
        "  \\setlength{\\tabcolsep}{3.5pt}" if wide else "  \\setlength{\\tabcolsep}{5pt}",
        f"  \\caption{{{latex_escape(caption)}}}",
        f"  \\label{{{latex_escape(spec['label'])}}}",
        "  \\begin{tabular}{l" + "c" * len(columns) + "}",
        "    \\toprule",
    ]
    group_labels = [c["dataset"] + (f" / {c['setting']}" if c.get("setting") else "") for c in columns]
    groups: list[tuple[str, int]] = []
    for label in group_labels:
        if groups and groups[-1][0] == label:
            groups[-1] = (label, groups[-1][1] + 1)
        else:
            groups.append((label, 1))
    if len(set(group_labels)) > 1 or (group_labels and group_labels[0] != "Overall"):
        header = ["Method"] + [f"\\multicolumn{{{span}}}{{c}}{{{latex_escape(label)}}}" for label, span in groups]
        lines.append("    " + " & ".join(header) + r" \\")
        start = 2
        rules = []
        for _, span in groups:
            rules.append(f"\\cmidrule(lr){{{start}-{start + span - 1}}}")
            start += span
        lines.append("    " + " ".join(rules))
        lines.append("    " + " & ".join([""] + [_metric_header(spec["metrics"][c["metric"]]) for c in columns]) + r" \\")
    else:
        lines.append("    " + " & ".join(["Method"] + [_metric_header(spec["metrics"][c["metric"]]) for c in columns]) + r" \\")
    lines.append("    \\midrule")

    styles = emphasis_map(spec)
    previous_group = None
    for row_index, row in enumerate(spec["rows"]):
        if previous_group is not None and row.get("group") != previous_group:
            lines.append("    \\addlinespace")
        values = []
        for column_index, (column, cell) in enumerate(zip(columns, row["cells"])):
            precision = spec["metrics"][column["metric"]]["precision"]
            value = _formatted_cell(cell, precision)
            style = styles.get((row_index, column_index))
            if style == "bold":
                value = f"\\textbf{{{value}}}"
            elif style == "underline":
                value = f"\\underline{{{value}}}"
            values.append(value)
        lines.append("    " + " & ".join([latex_escape(row["method"])] + values) + r" \\")
        previous_group = row.get("group")
    lines.extend(["    \\bottomrule", "  \\end{tabular}"])
    for note in spec.get("notes", []):
        lines.append(f"  \\parbox{{0.98\\linewidth}}{{\\footnotesize {latex_escape(note)}}}")
    lines.append(f"\\end{{{environment}}}")
    return "\n".join(lines) + "\n"


def render_preview_document() -> str:
    return "\n".join([
        r"\documentclass{article}",
        r"\usepackage[margin=1in]{geometry}",
        r"\usepackage{booktabs}",
        r"\begin{document}",
        r"\input{table.tex}",
        r"\end{document}",
        "",
    ])


def render_html(spec: dict[str, Any], caption: str) -> str:
    styles = emphasis_map(spec)
    group_labels = [c["dataset"] + (f" / {c['setting']}" if c.get("setting") else "") for c in spec["columns"]]
    groups: list[tuple[str, int]] = []
    for label in group_labels:
        if groups and groups[-1][0] == label:
            groups[-1] = (label, groups[-1][1] + 1)
        else:
            groups.append((label, 1))
    out = ["<!doctype html>", '<meta charset="utf-8">', "<style>",
           "table{border-collapse:collapse;font:14px system-ui;margin:2rem auto}caption{font-weight:600;margin:.8rem}th,td{padding:.45rem .7rem;text-align:center;border-bottom:1px solid #bbb}thead tr:first-child th{border-top:2px solid #222}tbody tr:last-child td{border-bottom:2px solid #222}th:first-child,td:first-child{text-align:left}",
           "</style>", "<table>", f"<caption>{html.escape(caption)}</caption>", "<thead>"]
    if len(set(group_labels)) > 1 or (group_labels and group_labels[0] != "Overall"):
        out.append("<tr><th rowspan=\"2\">Method</th>" + "".join(
            f'<th colspan="{span}">{html.escape(label)}</th>' for label, span in groups) + "</tr>")
        out.append("<tr>" + "".join(
            f"<th>{html.escape(spec['metrics'][c['metric']]['label'])} "
            f"{'↑' if spec['metrics'][c['metric']]['direction'] == 'max' else '↓'}</th>"
            for c in spec["columns"]) + "</tr>")
    else:
        out.append("<tr><th>Method</th>" + "".join(
            f"<th>{html.escape(spec['metrics'][c['metric']]['label'])} "
            f"{'↑' if spec['metrics'][c['metric']]['direction'] == 'max' else '↓'}</th>"
            for c in spec["columns"]) + "</tr>")
    out.extend(["</thead>", "<tbody>"])
    for row_index, row in enumerate(spec["rows"]):
        cells = []
        for column_index, (column, cell) in enumerate(zip(spec["columns"], row["cells"])):
            value = _formatted_cell(cell, spec["metrics"][column["metric"]]["precision"]).replace("$\\pm$", "±")
            style = styles.get((row_index, column_index))
            if style == "bold":
                value = f"<strong>{html.escape(value)}</strong>"
            elif style == "underline":
                value = f"<u>{html.escape(value)}</u>"
            else:
                value = html.escape(value)
            cells.append(f"<td>{value}</td>")
        out.append(f"<tr><td>{html.escape(row['method'])}</td>{''.join(cells)}</tr>")
    out.extend(["</tbody>", "</table>"])
    return "\n".join(out) + "\n"
