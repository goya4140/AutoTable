#!/usr/bin/env python3
"""Profile CSV/JSON experiment data and propose author questions."""
from __future__ import annotations
import argparse, csv, json, math
from collections import Counter
from pathlib import Path

ID_HINTS = {"method", "model", "variant", "dataset", "task", "split", "seed", "run"}

def load(path: Path):
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["rows"] if isinstance(data, dict) and "rows" in data else data

def number(v):
    try:
        x=float(v); return x if math.isfinite(x) else None
    except (TypeError, ValueError): return None

def main():
    p=argparse.ArgumentParser(); p.add_argument("input", type=Path); p.add_argument("--json", action="store_true")
    a=p.parse_args(); rows=load(a.input)
    if not isinstance(rows, list) or not rows: raise SystemExit("input must contain at least one row")
    keys=sorted({k for r in rows for k in r}); ids=[k for k in keys if k.lower() in ID_HINTS]
    numeric=[k for k in keys if k not in ids and sum(number(r.get(k)) is not None for r in rows) >= max(2, len(rows)//2)]
    seed=next((k for k in keys if k.lower() in {"seed","run","trial"}), None)
    missing={k:sum(r.get(k) in (None,"") for r in rows) for k in keys}
    dup=0
    if ids:
        c=Counter(tuple(str(r.get(k,"")) for k in ids if k != seed) for r in rows); dup=sum(v>1 for v in c.values())
    questions=[]
    if not seed or dup == 0: questions.append("Do you have repeated seeds/runs or sample-level predictions so uncertainty can be reported?")
    questions.append("For each numeric metric, is higher or lower better, and what are the units?")
    questions.append("What single scientific claim should a reader understand from this table?")
    out={"rows":len(rows),"columns":keys,"numeric_candidates":numeric,"identifier_candidates":ids,"missing":missing,"repeat_groups":dup,"blocking_questions":questions[:3],"design_proposal":{"layout":"group rows by method/condition and columns by dataset or metric family","precision":"infer per metric, then keep consistent","uncertainty":"mean ± SD when real repeats exist","emphasis":"best/second-best only within comparable groups","formats":["latex","html"]}}
    print(json.dumps(out, indent=2, ensure_ascii=False) if a.json else "\n".join([f"Rows: {out['rows']}",f"Numeric metrics: {', '.join(numeric) or 'none detected'}","Questions:"]+[f"- {q}" for q in questions[:3]]))
if __name__ == "__main__": main()
