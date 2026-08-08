#!/usr/bin/env python3
"""Render a contact sheet for visual review of pending discovery crops."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def render(queue, repo_root, out, limit=12, quality="all", columns=3):
    if quality not in {"all", "unflagged", "flagged"}:
        raise ValueError("quality must be all, unflagged, or flagged")
    selected = [record for record in queue if quality == "all" or bool(record.get("quality_flags")) == (quality == "flagged")][:limit]
    if not selected:
        raise ValueError("no audit records match the requested quality stratum")
    tile_width, tile_height, label_height = 520, 340, 54
    rows = math.ceil(len(selected) / columns)
    sheet = Image.new("RGB", (tile_width * columns, tile_height * rows), "white")
    draw = ImageDraw.Draw(sheet); font = ImageFont.load_default(size=14)
    for index, record in enumerate(selected):
        path = repo_root / record["crop_path"]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != record["crop_sha256"]:
            raise ValueError(f"crop hash mismatch: {record['id']}")
        image = Image.open(path).convert("RGB")
        image.thumbnail((tile_width - 20, tile_height - label_height - 14))
        x = (index % columns) * tile_width; y = (index // columns) * tile_height
        image_x = x + (tile_width - image.width) // 2; image_y = y + label_height + 5
        sheet.paste(image, (image_x, image_y))
        label = f"{record['id']} | {record['weak_purpose']} | {','.join(record['quality_flags']) or 'unflagged'}"
        draw.text((x + 8, y + 8), label[:72], fill="#202124", font=font)
        draw.line((x, y + tile_height - 1, x + tile_width, y + tile_height - 1), fill="#D9DEE7", width=1)
        draw.line((x + tile_width - 1, y, x + tile_width - 1, y + tile_height), fill="#D9DEE7", width=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return {"records": len(selected), "quality": quality, "columns": columns, "rows": rows, "output": str(out)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("queue", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=12)
    parser.add_argument("--quality", choices=["all", "unflagged", "flagged"], default="all")
    parser.add_argument("--columns", type=int, default=3)
    args = parser.parse_args()
    if args.limit < 1 or args.columns < 1:
        raise SystemExit("limit and columns must be positive")
    print(json.dumps(render(read_jsonl(args.queue), args.repo_root, args.out, args.limit, args.quality, args.columns), indent=2))


if __name__ == "__main__":
    main()
