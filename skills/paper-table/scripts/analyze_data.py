#!/usr/bin/env python3
"""Profile experiment data and emit a bounded, scientific inquiry plan."""
from __future__ import annotations
import argparse, csv, importlib.util, json, math
from collections import Counter
from pathlib import Path

ID_HINTS = {"method", "model", "variant", "dataset", "task", "split", "seed", "run"}

def load_advisor():
    path=Path(__file__).resolve().parent/"design_advisor.py"
    spec=importlib.util.spec_from_file_location("paper_table_analysis_advisor",path)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module

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
    if seed and dup > 0:
        add("uncertainty_kind","valuable_nonblocking",f"I found repeated rows indexed by {seed}. Are these independent runs, and should the final table report SD, SE, or a confidence interval?","Repeat identifiers support aggregation, but independence and uncertainty type still require author confirmation.",seed)
    else:
        add("uncertainty_source","valuable_nonblocking","Do you have repeated seeds/runs or sample-level predictions, and should uncertainty be SD, SE, or a confidence interval?","Real repeats support uncertainty; guessed variation must never be presented as observed.")
    add("claim","valuable_nonblocking","What single scientific claim should a reader understand from this table?","The claim guides layout and emphasis without changing data.")
    inquiry_plan=candidates[:3]
    questions=[item["question"] for item in inquiry_plan]
    semantics=context.get("metric_semantics",{}) if isinstance(context.get("metric_semantics",{}),dict) else {}
    draft_columns=[]
    for key in [*ids,*[item for item in numeric if item not in ids]]:
        if key in numeric:
            meta=semantics.get(key,{}) if isinstance(semantics.get(key,{}),dict) else {}
            draft_columns.append({"key":key,"label":key.replace("_"," ").title(),"kind":"metric","direction":meta.get("direction"),"unit":meta.get("unit")})
        else: draft_columns.append({"key":key,"label":key.replace("_"," ").title(),"kind":"text"})
    draft_spec={"columns":draft_columns,"rows":rows}
    if isinstance(context.get("claim"),str): draft_spec["claim"]=context["claim"]
    draft_case={"semantic_contract":{"comparison_groups":context.get("comparison_groups",[]),"rendering_constraints":context.get("rendering_constraints",{})}}
    visual=load_advisor().advise(draft_spec,draft_case)
    design_proposal={"primary_form":visual["primary_form"],**visual["proposal"],"precision":"infer per metric, then keep consistent","formats":["latex","html"]}
    out={"rows":len(rows),"columns":keys,"numeric_candidates":numeric,"identifier_candidates":ids,"missing":missing,"repeat_groups":dup,"inquiry_state":"awaiting_author" if any(q["importance"]=="blocking" for q in inquiry_plan) else "draft_ready","inquiry_plan":inquiry_plan,"blocking_questions":questions,"design_proposal":design_proposal,"visual_advice":visual}
    print(json.dumps(out, indent=2, ensure_ascii=False) if a.json else "\n".join([f"Rows: {out['rows']}",f"Numeric metrics: {', '.join(numeric) or 'none detected'}",f"Inquiry state: {out['inquiry_state']}","Questions:"]+[f"- [{q['importance']}] {q['question']}" for q in inquiry_plan]))
if __name__ == "__main__": main()
