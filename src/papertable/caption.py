from __future__ import annotations

from typing import Any


def build_caption(spec: dict[str, Any]) -> str:
    if spec.get("caption"):
        return str(spec["caption"])
    datasets = spec.get("datasets", [])
    metric_keys = list(spec["metrics"])
    metric_labels = [spec["metrics"][key]["label"] for key in metric_keys]
    system_count = len(spec["rows"]) if spec["orientation"] == "methods_rows" else len(spec["columns"])
    caption = (
        f"Main comparison of {system_count} systems on {', '.join(datasets)} "
        f"using {', '.join(metric_labels)}"
    )
    if not caption.endswith("."):
        caption += "."
    groups = list(dict.fromkeys(row.get("group") for row in spec["rows"] if row.get("group")))
    if spec.get("style", {}).get("row_group_style") == "band" and groups:
        caption += f" Systems are grouped into {', '.join(groups)}."
    ns = {cell["n"] for row in spec["rows"] for cell in row["cells"] if cell is not None}
    has_sd = any(cell["sd"] is not None for row in spec["rows"] for cell in row["cells"] if cell is not None)
    if has_sd:
        n_text = str(next(iter(ns))) if len(ns) == 1 else "the available"
        caption += f" Values report mean ± sample standard deviation over {n_text} runs."
    directions = {spec["metrics"][key]["direction"] for key in metric_keys}
    if directions == {"max"}:
        caption += " Higher values are better."
    elif directions == {"min"}:
        caption += " Lower values are better."
    else:
        caption += " Arrows indicate whether higher or lower values are better."
    if any(cell is None for row in spec["rows"] for cell in row["cells"]):
        caption += " Dashes denote unavailable results."
    emphasis = spec.get("emphasis", {})
    comparison_axis = "column" if spec["orientation"] == "methods_rows" else "row"
    scope = spec.get("comparison", {}).get("rank_scope_label")
    scope_text = f" among {scope}" if scope else ""
    if emphasis.get("best") == "bold" and emphasis.get("second") == "underline":
        caption += (
            f" Best and second-best results{scope_text} in each {comparison_axis} are bolded "
            "and underlined, respectively. Ties share the same marker."
        )
    elif emphasis.get("best") == "bold":
        caption += f" Best results{scope_text} in each {comparison_axis} are bolded."
    delta = spec.get("auxiliary", {}).get("delta")
    if delta:
        baseline = delta.get("baseline", {}).get("method", "the selected baseline")
        kind = "relative percentage" if delta.get("kind") == "relative_percent" else "absolute"
        caption += f" Parenthesized values report {kind} changes versus {baseline}."
    return caption
