#!/usr/bin/env python3
"""Render a Paper Table JSON spec to editable LaTeX and HTML."""
from __future__ import annotations
import argparse, html, json, math, re
from pathlib import Path

LATEX_ESC={"&":r"\&","%":r"\%","$":r"\$","#":r"\#","_":r"\_","{":r"\{","}":r"\}","~":r"\textasciitilde{}","^":r"\textasciicircum{}"}
def tex(s): return "".join(LATEX_ESC.get(c,c) for c in str(s))
def mean(cell):
    if isinstance(cell,(int,float)): return float(cell)
    if isinstance(cell,dict) and isinstance(cell.get("mean"),(int,float)): return float(cell["mean"])
    return None
def display(cell, precision):
    if cell is None: return "--"
    if isinstance(cell,dict):
        m=cell.get("mean");
        if m is None: return str(cell)
        for k,label in (("sd"," ± "),("se"," ± "),("ci90"," ± "),("ci95"," ± ")):
            if k in cell:
                v=cell[k]
                if k=="ci95" and isinstance(v,list): return f"{m:.{precision}f} [{v[0]:.{precision}f}, {v[1]:.{precision}f}]"
                return f"{m:.{precision}f}{label}{float(v):.{precision}f}"
        return f"{m:.{precision}f}"
    if isinstance(cell,(int,float)): return f"{cell:.{precision}f}"
    return str(cell)
def ranks(spec):
    out={}; scope=spec.get("emphasis",{}).get("scope","all")
    for col in spec["columns"]:
        if col.get("kind")!="metric": continue
        groups={}
        for i,row in enumerate(spec["rows"]):
            if not row.get("rank_eligible",True): continue
            v=mean(row.get(col["key"])); g=row.get("group","") if scope=="group" else "*"
            if v is not None: groups.setdefault(g,[]).append((v,i))
        for vals in groups.values():
            vals.sort(reverse=col.get("direction","max")!="min")
            unique=[]
            for v,_ in vals:
                if v not in unique: unique.append(v)
            for v,i in vals: out[(i,col["key"])]=1+unique.index(v)
    return out

def header_rows(cols, spec):
    """Return LaTeX/HTML headers, including optional nested column groups."""
    leaf=[tex(c["label"]+((" ↑" if c.get("direction")=="max" else " ↓") if c.get("kind")=="metric" else "")) for c in cols]
    html_leaf=[html.escape(c["label"])+(" ↑" if c.get("direction")=="max" else " ↓" if c.get("direction")=="min" else "") for c in cols]
    groups=[]
    for c in cols[1:]:
        group=c.get("group")
        if not groups or groups[-1][0]!=group: groups.append([group,1])
        else: groups[-1][1]+=1
    if not any(name for name,_ in groups):
        return [" & ".join(leaf)+r" \\"],"<tr>"+"".join(f"<th>{h}</th>" for h in html_leaf)+"</tr>"
    latex=[]; html_rows=[]; super_label=spec.get("column_supergroup")
    if super_label:
        latex.append(" & "+rf"\multicolumn{{{len(cols)-1}}}{{c}}{{{tex(super_label)}}} \\")
        latex.append(rf"\cmidrule(lr){{2-{len(cols)}}}")
        html_rows.append(f'<tr class="super"><th></th><th colspan="{len(cols)-1}">{html.escape(super_label)}</th></tr>')
    latex.append(" & ".join([""]+[rf"\multicolumn{{{span}}}{{c}}{{{tex(name or '')}}}" for name,span in groups])+r" \\")
    start=2; rules=[]
    for name,span in groups:
        if name: rules.append(rf"\cmidrule(lr){{{start}-{start+span-1}}}")
        start+=span
    if rules: latex.append(" ".join(rules))
    html_rows.append("<tr class=\"groups\"><th></th>"+"".join(f'<th colspan="{span}">{html.escape(name or "")}</th>' for name,span in groups)+"</tr>")
    latex.append(" & ".join(leaf)+r" \\")
    html_rows.append("<tr>"+"".join(f"<th>{h}</th>" for h in html_leaf)+"</tr>")
    return latex,"".join(html_rows)

def render(spec):
    ranking=ranks(spec); cols=spec["columns"]; rows=spec["rows"]; emph=spec.get("emphasis",{})
    aligns="l"+"r"*(len(cols)-1)
    latex_headers,html_headers=header_rows(cols,spec)
    lines=[r"\begin{table}[t]",r"\centering",r"\small",f"\\caption{{{tex(spec.get('caption',''))}}}",f"\\label{{{tex(spec.get('label','tab:results'))}}}",f"\\begin{{tabular}}{{{aligns}}}",r"\toprule",*latex_headers,r"\midrule"]
    last_group=None
    html_rows=[]
    for i,row in enumerate(rows):
        group=row.get("group")
        if last_group is not None and group!=last_group: lines.append(r"\addlinespace")
        cells=[]; hc=[]
        for c in cols:
            raw=display(row.get(c["key"]),int(c.get("precision",2))); rank=ranking.get((i,c["key"])); t=tex(raw)
            if rank==1 and emph.get("best","bold")=="bold": t=r"\textbf{"+t+"}"
            elif rank==2 and emph.get("second","underline")=="underline": t=r"\underline{"+t+"}"
            cells.append(t); hc.append(f'<td class="r{rank or 0}">{html.escape(raw)}</td>')
        lines.append(" & ".join(cells)+r" \\"); html_rows.append("<tr>"+"".join(hc)+"</tr>"); last_group=group
    lines += [r"\bottomrule",r"\end{tabular}"]
    for note in spec.get("notes",[]): lines.append(r"\par\vspace{2pt}\begin{minipage}{0.8\linewidth}\footnotesize "+tex(note)+r"\end{minipage}")
    lines.append(r"\end{table}")
    css="body{font-family:Georgia,serif;margin:32px;color:#171717}table{border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{padding:7px 12px;text-align:right}th:first-child,td:first-child{text-align:left}thead{border-top:2px solid;border-bottom:1px solid}.super th,.groups th{text-align:center;padding-top:3px;padding-bottom:3px}.groups th:not(:first-child){border-bottom:1px solid #777}tbody{border-bottom:2px solid}.r1{font-weight:700}.r2{text-decoration:underline}caption{font-weight:600;margin-bottom:10px}.notes{font-size:.86rem;margin-top:8px;max-width:900px}"
    note=" ".join(html.escape(n) for n in spec.get("notes",[]))
    page=f'<!doctype html><meta charset="utf-8"><style>{css}</style><table><caption>{html.escape(spec.get("caption",""))}</caption><thead>{html_headers}</thead><tbody>{"".join(html_rows)}</tbody></table><div class="notes">{note}</div>'
    return "\n".join(lines)+"\n",page
def main():
    p=argparse.ArgumentParser(); p.add_argument("spec",type=Path); p.add_argument("--out-dir",type=Path,required=True); a=p.parse_args()
    spec=json.loads(a.spec.read_text()); a.out_dir.mkdir(parents=True,exist_ok=True); latex,page=render(spec)
    (a.out_dir/"table.tex").write_text(latex); (a.out_dir/"table.html").write_text(page); print(a.out_dir)
if __name__=="__main__": main()
