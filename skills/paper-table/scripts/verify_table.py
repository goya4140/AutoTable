#!/usr/bin/env python3
"""Fail if numeric values in a table spec are absent from rendered LaTeX."""
import argparse, json, re
from pathlib import Path
def walk(x):
    if isinstance(x,dict):
        for k,v in x.items():
            if k != "precision": yield from walk(v)
    elif isinstance(x,list):
        for v in x: yield from walk(v)
    elif isinstance(x,(int,float)) and not isinstance(x,bool): yield x
def main():
    p=argparse.ArgumentParser(); p.add_argument("spec",type=Path); p.add_argument("rendered",type=Path); a=p.parse_args()
    spec=json.loads(a.spec.read_text()); text=a.rendered.read_text(); missing=[]
    for n in walk(spec.get("rows",[])):
        if not re.search(rf"(?<![\d.]){re.escape(str(n))}(?:0+)?(?!\d)",text): missing.append(n)
    report={"passed":not missing,"missing_numeric_values":missing,"checked":len(list(walk(spec.get('rows',[]))))}; print(json.dumps(report,indent=2)); raise SystemExit(0 if not missing else 1)
if __name__=="__main__": main()
