#!/usr/bin/env python3
"""Build the DIAMOND StatBench payload from the pinned author result file."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE_DIR = HERE / "cases/neurips24-diamond-atari"
AGGREGATOR_PATH = HERE.parents[1] / "skills/paper-table/scripts/aggregate_runs.py"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_aggregator():
    spec = importlib.util.spec_from_file_location("statbench_aggregate_runs", AGGREGATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_payload(source: dict, case: dict) -> dict:
    runs = [
        {"game": game, "seed_index": seed_index, "return": score}
        for game, scores in source.items()
        for seed_index, score in enumerate(scores)
    ]
    return {
        "schema_version": "paper-table-runs-v1",
        "title": "DIAMOND Atari 100k returns",
        "label": "tab:diamond-atari-raw-runs",
        "caption": "DIAMOND return on the 26 Atari 100k games, averaged over five independent training seeds.",
        "group_keys": [{"key": "game", "label": "Game"}],
        "run_id_key": "seed_index",
        "repeat_unit": "training seed",
        "independence": "independent",
        "reported_uncertainty": "none",
        "pairing": {"mode": "fixed_across_groups", "missing_policy": "error"},
        "metrics": [{"key": "return", "field": "return", "label": "DIAMOND (ours)", "direction": "max", "unit": "score", "precision": 1}],
        "runs": runs,
        "emphasis": {"best": "none", "second": "none", "scope": "all"},
        "notes": ["seed_index records array position in the author artifact; it is not an inferred internal seed value."],
        "provenance": {
            "paper_url": case["paper_url"],
            "source_repository": case["source"]["repository"],
            "source_commit": case["source"]["commit"],
            "source_path": case["source"]["path"],
            "source_sha256": case["source"]["sha256"]
        }
    }


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    case = json.loads((CASE_DIR / "case.json").read_text())
    source_path = CASE_DIR / case["source"]["local_path"]
    if digest(source_path) != case["source"]["sha256"]:
        raise SystemExit("author source hash mismatch")
    source = json.loads(source_path.read_text())
    if len(source) != 26 or any(len(scores) != 5 for scores in source.values()):
        raise SystemExit("expected 26 games with exactly five released seed results each")
    payload = build_payload(source, case)
    expected = load_aggregator().aggregate(payload)
    published = case["published_cells"]
    computed = {row["game"]: row["return"] for row in expected["rows"]}
    if computed != published:
        raise SystemExit("recomputed means do not match the published cells")
    write_json(CASE_DIR / case["derived_input"], payload)
    write_json(CASE_DIR / case["expected_output"], expected)
    print(json.dumps({"case": case["id"], "games": len(source), "runs": len(payload["runs"]), "published_cells_matched": len(computed)}, indent=2))


if __name__ == "__main__":
    main()
