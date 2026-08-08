#!/usr/bin/env python3
"""Build a canonical-table pair from RankUp's pinned author log and NeurIPS paper."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

import pypdfium2 as pdfium

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
CASE_ID="neurips24-rankup-utkface"
CASE_DIR=HERE/"cases"/CASE_ID
COMMIT="7ed6d267783d9dc8f99ae8188b126d125bf3ab79"
LOG_URL=f"https://raw.githubusercontent.com/pm25/semi-supervised-regression/{COMMIT}/results/classic_cv_average_log.csv"
PAPER_URL="https://proceedings.neurips.cc/paper_files/paper/2024/file/c26a8494fe31695db965ae8b7244b7c1-Paper-Conference.pdf"
LOG_SHA256="ddd78c263542108b952c8f1b07b7b7b0ce611c21b2fb6d70284809ba6640ebce"
PAPER_SHA256="98fdb7415c54d8a09e5e7ba46d44bf75e008d596f824db034f07f039f7ed297c"

METHODS=[
    ("Supervised","supervised_utkface_lb{labels}"),
    ("Π-Model","pimodel_utkface_lb{labels}"),
    ("Mean Teacher","meanteacher_utkface_lb{labels}"),
    ("CLSS","clss_utkface_lb{labels}"),
    ("UCVME","ucvme_utkface_lb{labels}"),
    ("MixMatch","mixmatch_utkface_lb{labels}"),
    ("RankUp (Ours)","rankup_utkface_lb{labels}"),
    ("RankUp + RDA (Ours)","rankuprda_utkface_lb{labels}"),
    ("Fully-Supervised","fullysupervised_utkface"),
]
METRICS=[("mae","min_MAE",2,"min"),("r2","max_R2",3,"max"),("srcc","max_SRCC",3,"max")]

def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url,timeout=60) as response:
        return response.read()

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def parse_cell(value: str, precision: int) -> dict:
    mean,sd=value.split("±")
    quantum=Decimal(1).scaleb(-precision)
    return {
        "mean":float(Decimal(mean).quantize(quantum,rounding=ROUND_HALF_EVEN)),
        "sd":float(Decimal(sd).quantize(quantum,rounding=ROUND_HALF_EVEN)),
    }

def build_x(log_bytes: bytes) -> tuple[dict,list[dict]]:
    source=list(csv.DictReader(io.StringIO(log_bytes.decode())))
    by_name={row["exp_name"]:row for row in source}
    selected=[]; rows=[]
    for label,pattern in METHODS:
        out={"group":"Upper bound" if label=="Fully-Supervised" else "Compared methods","method":label}
        if label=="Fully-Supervised": out["rank_eligible"]=False
        for labels in (50,250):
            key=pattern.format(labels=labels)
            record=by_name[key]
            if record not in selected: selected.append(record)
            for short,field,precision,_ in METRICS:
                out[f"{short}_{labels}"]=parse_cell(record[field],precision)
        rows.append(out)
    columns=[{"key":"method","label":"Method","kind":"text"}]
    for labels in (50,250):
        for short,_,precision,direction in METRICS:
            columns.append({"key":f"{short}_{labels}","label":short.upper() if short!="r2" else "R²","kind":"metric","direction":direction,"precision":precision,"group":f"Labels = {labels}"})
    x={
        "title":"RankUp on UTKFace",
        "label":"tab:rankup-utkface",
        "caption":"Comparison on UTKFace with 50 and 250 labeled samples (mean ± standard deviation over seeds 0, 1, and 2).",
        "column_supergroup":"UTKFace (Image Age Estimation)",
        "columns":columns,
        "rows":rows,
        "emphasis":{"best":"bold","second":"none","scope":"all"},
        "notes":["MAE is lower-is-better; R² and SRCC are higher-is-better.","Values are selected and rounded from the authors' pinned aggregate log; no values are inferred."],
        "provenance":{"observed":True,"input_tier":"canonical_table","source_commit":COMMIT,"uncertainty":"standard deviation","seeds":[0,1,2]},
    }
    return x,selected

def render_reference(pdf_bytes: bytes,path: Path) -> None:
    document=pdfium.PdfDocument(pdf_bytes)
    image=document[7].render(scale=2.5).to_pil()
    # Table body on official PDF page 8; coordinates are in the 1530×1980 render.
    image.crop((240,275,1250,685)).save(path,optimize=True)

def main() -> None:
    log_bytes=fetch(LOG_URL); pdf_bytes=fetch(PAPER_URL)
    if digest(log_bytes)!=LOG_SHA256: raise SystemExit("pinned RankUp log hash changed")
    if digest(pdf_bytes)!=PAPER_SHA256: raise SystemExit("official RankUp PDF hash changed")
    x,selected=build_x(log_bytes)
    CASE_DIR.mkdir(parents=True,exist_ok=True)
    render_reference(pdf_bytes,CASE_DIR/"y_reference.png")
    # Preserve the pinned artifact byte-for-byte so its local and remote hashes agree.
    (CASE_DIR/"source_log.csv").write_bytes(log_bytes)
    case={
        "id":CASE_ID,
        "input_tier":"canonical_table",
        "venue":"NeurIPS",
        "year":2024,
        "paper_url":PAPER_URL,
        "reference":{"page":8,"table":"Table 1","image":"y_reference.png","sha256":digest((CASE_DIR/"y_reference.png").read_bytes())},
        "source_artifacts":[
            {"role":"author aggregate log","url":LOG_URL,"path":"source_log.csv","sha256":LOG_SHA256,"commit":COMMIT},
            {"role":"published paper","url":PAPER_URL,"sha256":PAPER_SHA256}],
        "transformation":{"selection":"UTKFace, 50/250 labels, MAE/R²/SRCC","rounding":"decimal ROUND_HALF_EVEN to published precision","uncertainty":"author-described standard deviation over seeds 0, 1, 2"},
        "license":{"code_and_logs":"MIT","paper_excerpt":"source publication terms control","source_terms_control":True},
        "limitations":["The author repository releases three-seed aggregates, not the individual per-seed values; this case does not independently test aggregation correctness."],
    }
    ratings={"schema_version":"1.0","status":"unrated","required_raters":3,"dimensions":["typography","visual_hierarchy","readability","claim_salience","overall_aesthetics"],"ratings":[]}
    (CASE_DIR/"case.json").write_text(json.dumps(case,indent=2,ensure_ascii=False)+"\n")
    (CASE_DIR/"x.json").write_text(json.dumps(x,indent=2,ensure_ascii=False)+"\n")
    ratings_path=CASE_DIR/"ratings.json"
    if not ratings_path.exists():
        ratings_path.write_text(json.dumps(ratings,indent=2,ensure_ascii=False)+"\n")
    print(CASE_DIR)

if __name__=="__main__":
    main()
