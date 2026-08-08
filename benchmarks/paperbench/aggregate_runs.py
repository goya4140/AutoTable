#!/usr/bin/env python3
"""Aggregate long-form per-run JSON into the canonical PaperTable renderer spec."""
from __future__ import annotations

import argparse
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

def aggregate(payload: dict) -> dict:
    row_keys=payload["row_keys"]; metrics=payload["metrics"]; runs=payload["runs"]
    uncertainty=payload.get("uncertainty","sd")
    if uncertainty not in {"sd","se"}: raise ValueError("uncertainty must be sd or se")
    grouped=defaultdict(list)
    for run in runs:
        group=tuple(run[k["key"]] for k in row_keys)
        grouped[group].append(run)
    rows=[]; audit=[]
    for group,items in grouped.items():
        run_ids=[r[payload.get("run_id_key","seed")] for r in items]
        if len(run_ids)!=len(set(run_ids)): raise ValueError(f"duplicate run id in {group}")
        if len(items)<2: raise ValueError(f"at least two independent runs required for {group}")
        row={k["key"]:value for k,value in zip(row_keys,group)}
        for metric in metrics:
            values=[float(r[metric["key"]]) for r in items]
            sd=statistics.stdev(values)
            spread=sd if uncertainty=="sd" else sd/math.sqrt(len(values))
            row[metric["key"]]={"mean":statistics.fmean(values),uncertainty:spread}
            audit.append({"row":dict(zip((k["key"] for k in row_keys),group)),"metric":metric["key"],"n":len(values),"run_ids":run_ids,"mean":statistics.fmean(values),"sd":sd,"reported_uncertainty":uncertainty,"reported_value":spread})
        rows.append(row)
    columns=[{**k,"kind":"text"} for k in row_keys]+[{**m,"kind":"metric"} for m in metrics]
    return {
        "title":payload.get("title","Aggregated results"),
        "label":payload.get("label","tab:aggregated-results"),
        "caption":payload.get("caption",f"Mean ± {uncertainty} over independent runs."),
        "columns":columns,
        "rows":rows,
        "emphasis":payload.get("emphasis",{"best":"bold","second":"underline","scope":"all"}),
        "notes":payload.get("notes",[])+[f"Uncertainty is {uncertainty}; computed from independent run identifiers without imputation."],
        "provenance":{**payload.get("provenance",{}),"observed":True,"input_tier":"raw_runs","uncertainty":uncertainty},
        "aggregation_audit":audit,
    }

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("runs",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    result=aggregate(json.loads(args.runs.read_text()))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print(args.out)

if __name__=="__main__":
    main()
