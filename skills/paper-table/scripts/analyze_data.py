#!/usr/bin/env python3
"""Profile experiment data and emit a bounded, scientific inquiry plan."""
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
    p.add_argument("--context", type=Path, help="optional JSON with already supplied author metadata")
    a=p.parse_args(); rows=load(a.input)
    context=json.loads(a.context.read_text()) if a.context else {}
    if not isinstance(rows, list) or not rows: raise SystemExit("input must contain at least one row")
    keys=sorted({k for r in rows for k in r}); ids=[k for k in keys if k.lower() in ID_HINTS]
    numeric=[k for k in keys if k not in ids and sum(number(r.get(k)) is not None for r in rows) >= max(2, len(rows)//2)]
    seed=next((k for k in keys if k.lower() in {"seed","run","trial"}), None)
    missing={k:sum(r.get(k) in (None,"") for r in rows) for k in keys}
    dup=0
    if ids:
        c=Counter(tuple(str(r.get(k,"")) for k in ids if k != seed) for r in rows); dup=sum(v>1 for v in c.values())
    candidates=[]
    def add(field_id, importance, question, reason, detected=None):
        if field_id not in context:
            candidates.append({"id":field_id,"importance":importance,"ask_when_missing":True,"question":question,"reason":reason,"detected":detected})
    add("metric_semantics","blocking","For each numeric metric, is higher or lower better, and what unit should be shown?","Direction determines valid ranking; units prevent semantic mislabeling.",numeric)
    if len([k for k in ids if k != seed]) > 1:
        add("comparison_groups","blocking","Which rows are scientifically comparable for best/second-best emphasis?","Bolding across datasets, protocols, or supervision regimes can create a false claim.",[k for k in ids if k != seed])
    if not seed or dup == 0:
        add("uncertainty_source","valuable_nonblocking","Do you have repeated seeds/runs or sample-level predictions, and should uncertainty be SD, SE, or a confidence interval?","Real repeats support uncertainty; guessed variation must never be presented as observed.")
    add("claim","valuable_nonblocking","What single scientific claim should a reader understand from this table?","The claim guides layout and emphasis without changing data.")
    inquiry_plan=candidates[:3]
    questions=[item["question"] for item in inquiry_plan]
    out={"rows":len(rows),"columns":keys,"numeric_candidates":numeric,"identifier_candidates":ids,"missing":missing,"repeat_groups":dup,"inquiry_state":"awaiting_author" if any(q["importance"]=="blocking" for q in inquiry_plan) else "draft_ready","inquiry_plan":inquiry_plan,"blocking_questions":questions,"design_proposal":{"layout":"group rows by method/condition and columns by dataset or metric family","precision":"infer per metric, then keep consistent","uncertainty":"mean ± SD only when real repeats and the statistic type are known","emphasis":"best/second-best only within author-confirmed comparison groups","formats":["latex","html"]}}
    print(json.dumps(out, indent=2, ensure_ascii=False) if a.json else "\n".join([f"Rows: {out['rows']}",f"Numeric metrics: {', '.join(numeric) or 'none detected'}",f"Inquiry state: {out['inquiry_state']}","Questions:"]+[f"- [{q['importance']}] {q['question']}" for q in inquiry_plan]))
if __name__ == "__main__": main()
