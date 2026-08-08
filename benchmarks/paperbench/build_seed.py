#!/usr/bin/env python3
"""Materialize the curated NeurIPS mini benchmark from cached official PDFs/crops."""
from __future__ import annotations
import hashlib, json, shutil
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
SOURCE=ROOT/"benchmarks/neurips-tables/materialized/2024"

def digest(path: Path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    specs=sorted((HERE/"seed_specs").glob("*.json"))
    if not specs: raise SystemExit("no seed specs")
    for spec_path in specs:
        payload=json.loads(spec_path.read_text())
        case=payload["case"]; case_dir=HERE/"cases"/case["id"]; case_dir.mkdir(parents=True,exist_ok=True)
        source=SOURCE/f'{case["source_case_id"]}.png'
        if not source.exists(): raise SystemExit(f"materialize the NeurIPS source first: {source}")
        with Image.open(source) as im: im.crop(tuple(payload["crop"])).save(case_dir/"y_reference.png",optimize=True)
        case["reference"]["sha256"]=digest(case_dir/"y_reference.png")
        (case_dir/"case.json").write_text(json.dumps(case,indent=2,ensure_ascii=False)+"\n")
        (case_dir/"x.json").write_text(json.dumps(payload["x"],indent=2,ensure_ascii=False)+"\n")
        ratings={"schema_version":"1.0","status":"unrated","required_raters":3,"dimensions":["typography","visual_hierarchy","readability","claim_salience","overall_aesthetics"],"ratings":[]}
        rp=case_dir/"ratings.json"
        if not rp.exists(): rp.write_text(json.dumps(ratings,indent=2)+"\n")
        print(case["id"],case["reference"]["sha256"])

if __name__=="__main__": main()

