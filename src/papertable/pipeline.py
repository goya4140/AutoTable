from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .aggregate import aggregate
from .caption import build_caption
from .ingest import load_inputs
from .planner import plan_main_table
from .render import render_html, render_latex, render_preview_document
from .templates import resolve_config
from .verify import verify_spec


def _dump(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generate(
    inputs: list[str | Path], output_dir: str | Path, config: dict[str, Any] | None = None,
    template: str | None = None,
) -> dict[str, Any]:
    config = resolve_config(config, template)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    observations = load_inputs(inputs, config)
    aggregates = aggregate(observations)
    spec = plan_main_table(aggregates, config)
    caption = build_caption(spec)
    spec["caption"] = caption
    verification = verify_spec(spec)
    if not verification["valid"]:
        raise ValueError("invalid table spec: " + "; ".join(verification["errors"]))

    _dump(output / "observations.json", [item.to_dict() for item in observations])
    _dump(output / "aggregates.json", [item.to_dict() for item in aggregates])
    _dump(output / "table-spec.json", spec)
    (output / "caption.txt").write_text(caption + "\n", encoding="utf-8")
    latex = render_latex(spec, caption)
    html = render_html(spec, caption)
    (output / "table.tex").write_text(latex, encoding="utf-8")
    (output / "table.html").write_text(html, encoding="utf-8")
    (output / "preview.tex").write_text(render_preview_document(), encoding="utf-8")

    planned = sum(cell is not None for row in spec["rows"] for cell in row["cells"])
    manifest = {
        "schema_version": "paper-table-manifest-v1",
        "inputs": [str(Path(path)) for path in inputs],
        "observation_count": len(observations),
        "aggregate_count": len(aggregates),
        "displayed_cell_count": planned,
        "method_count": len(spec["methods"]),
        "displayed_system_count": len(spec["rows"]) if spec["orientation"] == "methods_rows" else len(spec["columns"]),
        "column_count": len(spec["columns"]),
        "template_id": spec["template_id"],
        "orientation": spec["orientation"],
        "ranking_scope": spec.get("comparison", {}).get("rank_scope_label", "all displayed systems"),
        "auxiliary_display": list(spec.get("auxiliary", {})),
        "omitted_columns": spec["omitted_columns"],
        "warnings": spec["warnings"],
        "verification": verification,
        "artifacts": ["observations.json", "aggregates.json", "table-spec.json", "table.tex", "table.html", "caption.txt", "preview.tex"],
    }
    _dump(output / "manifest.json", manifest)
    return manifest
