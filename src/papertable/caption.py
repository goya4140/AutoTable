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
        f"using {', '.join(metric_labels)}."
    )
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
    emphasis = spec.get("emphasis", {})
    comparison_axis = "column" if spec["orientation"] == "methods_rows" else "row"
    if emphasis.get("best") == "bold" and emphasis.get("second") == "underline":
        caption += (
            f" Best and second-best results in each {comparison_axis} are bolded "
            "and underlined, respectively."
        )
    elif emphasis.get("best") == "bold":
        caption += f" Best results in each {comparison_axis} are bolded."
    return caption
