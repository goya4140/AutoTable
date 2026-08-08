#!/usr/bin/env python3
"""Materialize TableVisBench into an ignored local cache without relicensing it."""
from __future__ import annotations
import argparse, json, urllib.request
from pathlib import Path

BASE="https://huggingface.co/datasets/lntzm/TableVisBench/resolve/main"
HERE=Path(__file__).resolve().parent
def get(url): return urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"PaperTable benchmark adapter/0.2"}),timeout=60).read()
def main():
    p=argparse.ArgumentParser(); p.add_argument("--limit",type=int,default=20); a=p.parse_args()
    cache=HERE/"cache/tablevisbench"; cache.mkdir(parents=True,exist_ok=True)
    lines=get(f"{BASE}/eval_data.jsonl").decode().splitlines(); out=[]
    for raw in lines[:a.limit]:
        row=json.loads(raw); iid=str(row["id"]); image_name=f"{iid}.jpg"; image_url=f"{BASE}/images/{image_name}"
        image_path=cache/image_name
        if not image_path.exists(): image_path.write_bytes(get(image_url))
        case={"id":f"tablevisbench-{iid}","input_tier":"canonical_table","source_dataset":"TableVisBench","source_license":"CC-BY-NC-4.0","topic":row.get("topic"),"x_table":row.get("table"),"y_path":str(image_path),"y_url":image_url}
        out.append(case)
    manifest=cache/"manifest.jsonl"; manifest.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in out)); print(manifest,len(out))
if __name__=="__main__": main()
