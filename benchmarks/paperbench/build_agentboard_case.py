#!/usr/bin/env python3
"""Build a canonical-table pair from AgentBoard's pinned author-site JSON."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

import pypdfium2 as pdfium

from contracts import contract_for, enrich_spec

HERE = Path(__file__).resolve().parent
CASE_ID = "neurips24-agentboard-proprietary"
CASE_DIR = HERE / "cases" / CASE_ID
SITE_COMMIT = "5d72338a19f6b177cfe8d77d586421961b90aa8e"
DATA_URL = (
    "https://raw.githubusercontent.com/hkust-nlp/hkust-nlp.github.io/"
    f"{SITE_COMMIT}/agentboard/data/To_Release/main_data_new.json"
)
PAPER_URL = "https://proceedings.neurips.cc/paper_files/paper/2024/file/877b40688e330a0e2a3fc24084208dfa-Paper-Datasets_and_Benchmarks_Track.pdf"
DATA_SHA256 = "00970015d126d234d3574dd2f8286f2725679f96eacf4d843eded8ac9b0ffbb2"
PAPER_SHA256 = "72154c4c71d0295deee5f9266a40db63fa4111f4b167f8ed17fd61556f9d8220"

TASKS = [
    ("alf", "ALF", "AlfWorld", "Embodied AI"),
    ("sw", "SW", "ScienceWorld", "Embodied AI"),
    ("ba", "BA", "BabyAI", "Embodied AI"),
    ("jc", "JC", "Jericho", "Game"),
    ("pl", "PL", "PDDL", "Game"),
    ("ws", "WS", "WebShop", "Web"),
    ("wa", "WA", "WebArena", "Web"),
    ("tq", "TQ", "Tool-Query", "Tool"),
    ("to", "TO", "Tool-Operation", "Tool"),
    ("avg", "Avg.", "Avg", "Average"),
]
MODELS = ["GPT-4", "Claude2"]


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def percentage(value: str) -> float:
    if not value.endswith("%"):
        raise ValueError(f"expected percentage string, got {value!r}")
    return float(value[:-1])


def build_x(data_bytes: bytes) -> dict:
    source = json.loads(data_bytes)
    by_model = {record["model"]: record for record in source}
    missing = set(MODELS) - set(by_model)
    if missing:
        raise ValueError(f"pinned source lacks required models: {sorted(missing)}")

    columns = [{"key": "model", "label": "Model", "kind": "text"}]
    for short, label, _source_key, group in TASKS:
        columns.extend([
            {"key": f"progress_{short}", "label": "Progress", "kind": "metric", "direction": "max", "precision": 1, "group": label, "supergroup": group},
            {"key": f"success_{short}", "label": "Success", "kind": "metric", "direction": "max", "precision": 1, "group": label, "supergroup": group},
        ])

    rows = []
    for model in MODELS:
        source_tasks = by_model[model]["tasks"]
        row = {"model": model, "group": "Proprietary models"}
        for short, _label, source_key, _group in TASKS:
            row[f"progress_{short}"] = percentage(source_tasks[source_key]["score"])
            row[f"success_{short}"] = percentage(source_tasks[source_key]["accuracy"])
        rows.append(row)

    spec = {
        "title": "AgentBoard proprietary-model performance",
        "label": "tab:agentboard-proprietary",
        "caption": "AgentBoard progress rate and success rate for GPT-4 and Claude2 across nine environments and their average.",
        "columns": columns,
        "rows": rows,
        "emphasis": {"best": "bold", "second": "none", "scope": "all"},
        "notes": [
            "All values are percentages; higher is better.",
            "The paired columns decompose each published A/B cell into progress rate and success rate.",
            "Only the two contiguous proprietary-model rows supported exactly by the pinned author JSON are included.",
        ],
        "provenance": {
            "observed": True,
            "input_tier": "canonical_table",
            "source_commit": SITE_COMMIT,
            "aggregation_status": "author_aggregate",
            "selection": "Table 3 header and first two contiguous rows",
        },
    }
    return enrich_spec(CASE_ID, spec)


def render_reference(pdf_bytes: bytes, path: Path) -> None:
    document = pdfium.PdfDocument(pdf_bytes)
    image = document[6].render(scale=2.5).to_pil()
    # Official page 7: Table 3 caption, full header, GPT-4 row, and Claude2 row.
    image.crop((230, 150, 1400, 412)).save(path, optimize=True)


def main() -> None:
    data_bytes = fetch(DATA_URL)
    paper_bytes = fetch(PAPER_URL)
    if digest(data_bytes) != DATA_SHA256:
        raise SystemExit("pinned AgentBoard author data hash changed")
    if digest(paper_bytes) != PAPER_SHA256:
        raise SystemExit("official AgentBoard PDF hash changed")

    CASE_DIR.mkdir(parents=True, exist_ok=True)
    render_reference(paper_bytes, CASE_DIR / "y_reference.png")
    spec = build_x(data_bytes)
    reference_sha = digest((CASE_DIR / "y_reference.png").read_bytes())
    case = {
        "schema_version": "2.0",
        "id": CASE_ID,
        "task": "experimental-data-to-publication-table",
        "input_tier": "canonical_table",
        "venue": "NeurIPS",
        "year": 2024,
        "paper_url": PAPER_URL,
        "reference": {"page": 7, "table": "Table 3 (header and first two rows)", "image": "y_reference.png", "sha256": reference_sha},
        "source_artifacts": [
            {"role": "author aggregate data", "url": DATA_URL, "sha256": DATA_SHA256, "commit": SITE_COMMIT, "redistributed": False},
            {"role": "published paper", "url": PAPER_URL, "sha256": PAPER_SHA256},
        ],
        "transformation": {
            "selection": "GPT-4 and Claude2, all nine environments plus Avg.",
            "cell_mapping": "score -> Progress and accuracy -> Success; strip percent sign without rescaling",
            "rounding": "none; preserve the author's one-decimal values",
            "uncertainty": "not present in this Table 3 excerpt",
        },
        "license": {"author_site_data": "source repository terms control", "paper_excerpt": "source publication terms control", "source_terms_control": True},
        "semantic_contract": contract_for(CASE_ID),
        "limitations": [
            "The pinned author-site JSON contains 13 models while the final paper contains 19; this strict case therefore uses only the first two contiguous rows, which the artifact supports exactly.",
            "The author artifact contains aggregate point estimates rather than per-example trajectories, so this case does not test aggregation correctness or uncertainty estimation.",
        ],
    }
    ratings = {"schema_version": "1.0", "status": "unrated", "required_raters": 3, "dimensions": ["typography", "visual_hierarchy", "readability", "claim_salience", "overall_aesthetics"], "ratings": []}
    (CASE_DIR / "case.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n")
    (CASE_DIR / "x.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    ratings_path = CASE_DIR / "ratings.json"
    if not ratings_path.exists():
        ratings_path.write_text(json.dumps(ratings, indent=2, ensure_ascii=False) + "\n")
    print(CASE_DIR)


if __name__ == "__main__":
    main()
