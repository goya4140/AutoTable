from __future__ import annotations

from typing import Any


def build_caption(spec: dict[str, Any]) -> str:
    if spec.get("caption"):
        return str(spec["caption"])
    datasets = list(dict.fromkeys(c["dataset"] for c in spec["columns"]))
    metric_keys = list(dict.fromkeys(c["metric"] for c in spec["columns"]))
    metric_labels = [spec["metrics"][key]["label"] for key in metric_keys]
    caption = (
        f"Main comparison of {len(spec['rows'])} methods on {', '.join(datasets)} "
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
    if emphasis.get("best") == "bold" and emphasis.get("second") == "underline":
        caption += " Best and second-best results in each column are bolded and underlined, respectively."
    elif emphasis.get("best") == "bold":
        caption += " Best results in each column are bolded."
    return caption
