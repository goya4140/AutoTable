from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .ingest import InputError
from .pipeline import generate
from .templates import available_templates


def _config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config root must be a JSON object")
    return data


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="paper2table", description="Experiment files → caption + table")
    sub = root.add_subparsers(dest="command", required=True)
    generate_parser = sub.add_parser("generate", help="run the complete deterministic pipeline")
    generate_parser.add_argument("inputs", nargs="+", help="CSV, TSV, JSON, or JSONL experiment files")
    generate_parser.add_argument("--config", help="JSON design/semantic config")
    generate_parser.add_argument("--template", help="research-backed main-table template ID or JSON path")
    generate_parser.add_argument("--out", default="output/main-table", help="output directory")
    sub.add_parser("list-templates", help="list reusable main-table design templates")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            manifest = generate(args.inputs, args.out, _config(args.config), args.template)
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
        if args.command == "list-templates":
            print(json.dumps(available_templates(), ensure_ascii=False, indent=2))
            return 0
    except (InputError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    return 1
