#!/usr/bin/env python3
"""Generate y' from x and compute objective fidelity plus clearly labeled visual proxies."""
from __future__ import annotations
import csv, hashlib, importlib.util, json, math, re, subprocess, sys
from collections import Counter
from pathlib import Path
from PIL import Image, ImageChops, ImageStat

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"output/paperbench"
RENDER=ROOT/"skills/paper-table/scripts/render_table.py"
PDFTOPPM=Path("/Users/wlh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdftoppm")

def load_contract_evaluator():
    spec=importlib.util.spec_from_file_location("paperbench_contract_eval",HERE/"contract_eval.py")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module.evaluate

def norm(v): return re.sub(r"\s+"," ",str(v).replace("−","-").replace("–","-")).strip().lower()
def cells(x):
    for c in x["columns"]: yield c["label"]
    for row in x["rows"]:
        for c in x["columns"]:
            v=row.get(c["key"])
            if isinstance(v,dict):
                yield v.get("mean")
                for k in ("sd","se","ci90","ci95"):
                    if k in v: yield v[k]
            elif v is not None: yield v
def numbers(values):
    out=[]
    for v in values:
        if isinstance(v,(int,float)): out.append(str(v))
        elif isinstance(v,list): out += [str(z) for z in v if isinstance(z,(int,float))]
    return out
def source_body_numbers(x):
    out=[]
    for row in x["rows"]:
        for c in x["columns"]:
            v=row.get(c["key"])
            if isinstance(v,str): out.extend(number_tokens(v))
    return out
def number_tokens(text): return re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?",text.replace("−","-"))
def num_norm(x):
    try: return f"{float(x):.12g}"
    except ValueError: return norm(x)
def multiset_recall(expected,actual):
    e=Counter(num_norm(x) for x in expected); a=Counter(num_norm(x) for x in actual); hit=sum((e&a).values())
    return hit/max(1,sum(e.values())),hit/max(1,sum(a.values())),sum((a-e).values())
def autocrop(path: Path):
    im=Image.open(path).convert("RGB"); bg=Image.new("RGB",im.size,"white"); diff=ImageChops.difference(im,bg); bbox=diff.getbbox()
    if bbox: im.crop((max(0,bbox[0]-12),max(0,bbox[1]-12),min(im.width,bbox[2]+12),min(im.height,bbox[3]+12))).save(path)
def visual_proxy(path: Path,reference_aspect=None):
    im=Image.open(path).convert("L"); stat=ImageStat.Stat(im); contrast=min(1.0,stat.stddev[0]/64)
    hist=im.histogram(); ink=1-sum(hist[245:])/max(1,im.width*im.height)
    density=math.exp(-abs(ink-.18)/.18)
    aspect=im.width/max(1,im.height); aspect_match=1.0 if reference_aspect is None else math.exp(-abs(math.log(max(.01,aspect/reference_aspect))))
    return {"contrast_proxy":round(contrast,4),"density_proxy":round(density,4),"aspect_match_proxy":round(aspect_match,4),"aspect_ratio":round(aspect,4)}
def render(case_dir: Path,out: Path):
    out.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,str(RENDER),str(case_dir/"x.json"),"--out-dir",str(out)],check=True,capture_output=True,text=True)
    wrapper="\\documentclass{article}\n\\usepackage[margin=0.5in]{geometry}\n\\usepackage{booktabs}\n\\usepackage{fontspec}\n\\pagestyle{empty}\n\\begin{document}\n\\input{table.tex}\n\\end{document}\n"
    (out/"preview.tex").write_text(wrapper)
    subprocess.run(["latexmk","-xelatex","-interaction=nonstopmode","-halt-on-error","preview.tex"],cwd=out,check=True,capture_output=True,text=True)
    subprocess.run([str(PDFTOPPM),"-png","-r","180","-singlefile","preview.pdf","y_prime"],cwd=out,check=True,capture_output=True,text=True)
    autocrop(out/"y_prime.png")
def main():
    evaluate_contract=load_contract_evaluator()
    rows=[]
    for case_dir in sorted((HERE/"cases").iterdir()):
        if not case_dir.is_dir(): continue
        case=json.loads((case_dir/"case.json").read_text()); x=json.loads((case_dir/"x.json").read_text()); out=OUT/case["id"]
        render(case_dir,out); code=(out/"table.tex").read_text()
        expected_cells=[v for v in cells(x) if v is not None]; expected_nums=numbers(expected_cells)+source_body_numbers(x)
        body=code.split("\\midrule",1)[1].split("\\bottomrule",1)[0]; actual_nums=number_tokens(body)
        nr,np,hall=multiset_recall(expected_nums,actual_nums)
        plain_code=code.replace("\\%","%").replace("\\_","_").replace("\\&","&")
        code_nums={num_norm(v) for v in number_tokens(code)}
        flat_expected=[v for v in expected_cells if not isinstance(v,list)]
        text_hits=sum((num_norm(v) in code_nums) if isinstance(v,(int,float)) else (norm(v) in norm(plain_code)) for v in flat_expected); cr=text_hits/max(1,len(flat_expected))
        headers=[c["label"] for c in x["columns"]]; hr=sum(norm(h) in norm(plain_code) for h in headers)/len(headers)
        ref=Image.open(case_dir/case["reference"]["image"]); ref_aspect=ref.width/ref.height
        contract_result=evaluate_contract(x,x,case)
        semantic_gate=contract_result["passed_scientific_gate"]
        metrics={"id":case["id"],"input_tier":case["input_tier"],"numeric_recall":round(nr,4),"numeric_precision":round(np,4),"hallucinated_numeric_tokens":hall,"cell_recall":round(cr,4),"header_recall":round(hr,4),"render_success":True,"numeric_fidelity_gate":nr==1 and np==1 and hall==0,"semantic_contract_gate":semantic_gate,"full_contract_gate":contract_result["passed_full_contract"],"scientific_gate":nr==1 and np==1 and hall==0 and semantic_gate,"semantic_contract_categories":contract_result["category_counts"],"reference_visual_proxy":visual_proxy(case_dir/case["reference"]["image"]),"generated_visual_proxy":visual_proxy(out/"y_prime.png",ref_aspect)}
        ratings=json.loads((case_dir/"ratings.json").read_text()); metrics["aesthetic_rating_status"]=ratings["status"]
        if ratings.get("ratings"):
            dims=ratings["dimensions"]
            metrics["pilot_rubric"]={side:{d:round(sum(r[side][d] for r in ratings["ratings"])/len(ratings["ratings"]),3) for d in dims} for side in ("reference","generated")}
        (out/"metrics.json").write_text(json.dumps(metrics,indent=2)+"\n"); rows.append(metrics)
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"summary.json").write_text(json.dumps(rows,indent=2)+"\n")
    with (OUT/"summary.csv").open("w",newline="") as f:
        fields=["id","input_tier","numeric_recall","numeric_precision","hallucinated_numeric_tokens","cell_recall","header_recall","render_success","numeric_fidelity_gate","semantic_contract_gate","scientific_gate","aesthetic_rating_status"]
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    print(json.dumps(rows,indent=2))
if __name__=="__main__": main()
