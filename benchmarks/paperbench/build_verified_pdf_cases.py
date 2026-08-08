#!/usr/bin/env python3
"""Build manually verified PaperBench pairs from pinned official PDF pages."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from contracts import contract_for, enrich_spec

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEFAULT_CACHE = ROOT / "benchmarks/neurips-tables/cache/2024"
DEFAULT_PDFTOPPM = Path(
    "/Users/wlh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm"
)
RATINGS = {
    "schema_version": "1.0",
    "status": "unrated",
    "required_raters": 3,
    "dimensions": ["typography", "visual_hierarchy", "readability", "claim_salience", "overall_aesthetics"],
    "ratings": [],
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_pdftoppm(explicit: Path | None) -> str:
    if explicit and explicit.is_file():
        return str(explicit)
    if DEFAULT_PDFTOPPM.is_file():
        return str(DEFAULT_PDFTOPPM)
    executable = shutil.which("pdftoppm")
    if executable:
        return executable
    raise SystemExit("pdftoppm is required; pass --pdftoppm /path/to/pdftoppm")


def render_crop(pdf: Path, page: int, crop: list[int], output: Path, pdftoppm: str) -> None:
    with tempfile.TemporaryDirectory(prefix="papertable-pdf-") as tmp:
        prefix = Path(tmp) / "page"
        subprocess.run(
            [pdftoppm, "-png", "-r", "144", "-f", str(page), "-l", str(page), "-singlefile", str(pdf), str(prefix)],
            check=True,
            capture_output=True,
            text=True,
        )
        with Image.open(prefix.with_suffix(".png")) as image:
            if image.size != (1224, 1584):
                raise ValueError(f"{pdf.name}: expected a 1224x1584 page at 144 dpi, got {image.size}")
            image.crop(tuple(crop)).save(output, optimize=True)


def build(spec_path: Path, cache: Path, pdftoppm: str) -> str:
    payload = json.loads(spec_path.read_text())
    case = payload["case"]
    case_id = case["id"]
    pdf = cache / payload["source_pdf"]
    if not pdf.is_file():
        raise FileNotFoundError(f"missing pinned source PDF: {pdf}")
    if digest(pdf) != payload["source_pdf_sha256"]:
        raise ValueError(f"{case_id}: source PDF hash mismatch")

    case_dir = HERE / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    reference = case_dir / "y_reference.png"
    render_crop(pdf, case["reference"]["page"], payload["page_crop_144dpi"], reference, pdftoppm)

    case["schema_version"] = "2.0"
    case["task"] = "experimental-data-to-publication-table"
    case["reference"]["sha256"] = digest(reference)
    case["reference"]["render_dpi"] = 144
    case["reference"]["page_crop_px"] = payload["page_crop_144dpi"]
    case["semantic_contract"] = contract_for(case_id)
    case["source_artifacts"] = [{
        "kind": "published_pdf",
        "url": case["paper_url"],
        "sha256": payload["source_pdf_sha256"],
        "redistributed": False,
    }]

    spec = enrich_spec(case_id, payload["x"])
    (case_dir / "case.json").write_text(json.dumps(case, indent=2, ensure_ascii=False) + "\n")
    (case_dir / "x.json").write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n")
    (case_dir / "ratings.json").write_text(json.dumps(RATINGS, indent=2) + "\n")
    return case_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--pdftoppm", type=Path)
    args = parser.parse_args()
    pdftoppm = find_pdftoppm(args.pdftoppm)
    specs = sorted((HERE / "verified_specs").glob("*.json"))
    if not specs:
        raise SystemExit("no verified PDF specs")
    for spec in specs:
        print(build(spec, args.cache_dir, pdftoppm))


if __name__ == "__main__":
    main()
