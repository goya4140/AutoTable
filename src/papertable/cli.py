from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .ingest import InputError
from .pipeline import generate


def _config(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    with Path(path).open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("config root must be a JSON object")
    return data


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="papertable", description="Experimental data → main table + caption")
    sub = root.add_subparsers(dest="command", required=True)
    generate_parser = sub.add_parser("generate", help="run the complete deterministic pipeline")
    generate_parser.add_argument("inputs", nargs="+", help="CSV, TSV, JSON, or JSONL experiment files")
    generate_parser.add_argument("--config", help="JSON design/semantic config")
    generate_parser.add_argument("--out", default="output/main-table", help="output directory")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            manifest = generate(args.inputs, args.out, _config(args.config))
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0
    except (InputError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}")
        return 2
    return 1

