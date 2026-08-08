#!/usr/bin/env python3
"""Render a Paper Table JSON spec to editable LaTeX and HTML."""
from __future__ import annotations
import argparse, html, json
from pathlib import Path

LATEX_ESC={"&":r"\&","%":r"\%","$":r"\$","#":r"\#","_":r"\_","{":r"\{","}":r"\}","~":r"\textasciitilde{}","^":r"\textasciicircum{}"}
FONT_SIZES={"small":15,"footnotesize":13,"scriptsize":11}

def layout(spec):
    value={"font_size":"small","column_padding_pt":6.0,"row_stretch":1.0,**spec.get("layout",{})}
    if value["font_size"] not in FONT_SIZES: raise ValueError("layout.font_size must be small, footnotesize, or scriptsize")
    if not isinstance(value["column_padding_pt"],(int,float)) or not 1.5<=value["column_padding_pt"]<=10: raise ValueError("layout.column_padding_pt must be between 1.5 and 10")
    if not isinstance(value["row_stretch"],(int,float)) or not .8<=value["row_stretch"]<=1.5: raise ValueError("layout.row_stretch must be between 0.8 and 1.5")
    text_width=value.get("text_column_width_pt")
    if text_width is not None and (not isinstance(text_width,(int,float)) or not 45<=text_width<=160): raise ValueError("layout.text_column_width_pt must be between 45 and 160")
    panels=value.get("panels")
    if panels is not None:
        metric_keys=[column["key"] for column in spec.get("columns",[]) if column.get("kind")=="metric"]
        if not isinstance(panels,list) or len(panels)<2: raise ValueError("layout.panels must contain at least two panels")
        covered=[]
        for panel in panels:
            if not isinstance(panel,dict) or not isinstance(panel.get("label"),str) or not panel["label"].strip(): raise ValueError("each panel requires a non-empty label")
            if not isinstance(panel.get("metric_keys"),list) or not panel["metric_keys"]: raise ValueError("each panel requires metric_keys")
            covered.extend(panel["metric_keys"])
        if covered!=metric_keys or len(covered)!=len(set(covered)): raise ValueError("panel metric_keys must cover every metric exactly once in column order")
    return value

def layout_commands(spec):
    value=layout(spec)
    return [rf"\{value['font_size']}",rf"\setlength{{\tabcolsep}}{{{value['column_padding_pt']:g}pt}}",rf"\renewcommand{{\arraystretch}}{{{value['row_stretch']:g}}}"]
def tex(s): return "".join(LATEX_ESC.get(c,c) for c in str(s))
def wrapped_tex(value,width): return rf"\parbox[t]{{{width:g}pt}}{{\raggedright {tex(value)}}}" if width else tex(value)
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
    text_width=layout(spec).get("text_column_width_pt")
    leaf=[wrapped_tex(c["label"]+((" ↑" if c.get("direction")=="max" else " ↓") if c.get("kind")=="metric" else ""),text_width if c.get("kind")!="metric" else None) for c in cols]
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

def tabular(spec):
    ranking=ranks(spec); cols=spec["columns"]; rows=spec["rows"]; emph=spec.get("emphasis",{})
    aligns="l"+"r"*(len(cols)-1)
    latex_headers,html_headers=header_rows(cols,spec)
    lines=[f"\\begin{{tabular}}{{{aligns}}}",r"\toprule",*latex_headers,r"\midrule"]
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
            if c.get("kind")!="metric" and layout(spec).get("text_column_width_pt"): t=wrapped_tex(raw,layout(spec)["text_column_width_pt"])
            cells.append(t); hc.append(f'<td class="r{rank or 0}">{html.escape(raw)}</td>')
        lines.append(" & ".join(cells)+r" \\"); html_rows.append("<tr>"+"".join(hc)+"</tr>"); last_group=group
    lines += [r"\bottomrule",r"\end{tabular}"]
    return lines,html_headers,html_rows

def latex_tabular(spec):
    if spec.get("layout",{}).get("panels"): raise ValueError("latex_tabular requires a single-panel projected spec")
    return "\n".join(tabular(spec)[0])+"\n"

def projected_panels(spec):
    panels=layout(spec).get("panels")
    if not panels: return [(None,spec)]
    text_columns=[column for column in spec["columns"] if column.get("kind")!="metric"]
    metric_map={column["key"]:column for column in spec["columns"] if column.get("kind")=="metric"}
    projected=[]
    for panel in panels:
        child={key:value for key,value in spec.items()}
        child["columns"]=[*text_columns,*[dict(metric_map[key]) for key in panel["metric_keys"]]]
        child["layout"]={key:value for key,value in spec.get("layout",{}).items() if key!="panels"}
        groups={column.get("group") for column in child["columns"] if column.get("kind")=="metric"}
        if len(groups)==1 and next(iter(groups)):
            for column in child["columns"]:
                if column.get("kind")=="metric": column.pop("group",None)
            child.pop("column_supergroup",None)
        projected.append((panel["label"],child))
    return projected

def render(spec):
    value=layout(spec)
    panels=projected_panels(spec)
    lines=[r"\begin{table}[t]",r"\centering",*layout_commands(spec),f"\\caption{{{tex(spec.get('caption',''))}}}",f"\\label{{{tex(spec.get('label','tab:results'))}}}"]
    html_sections=[]
    for index,(panel_label,child) in enumerate(panels):
        tabular_lines,html_headers,html_rows=tabular(child)
        if panel_label: lines.extend([rf"\textbf{{{tex(panel_label)}}}\par\smallskip",*tabular_lines])
        else: lines.extend(tabular_lines)
        if index<len(panels)-1: lines.append(r"\par\medskip")
        table_caption=html.escape(panel_label or spec.get("caption",""))
        html_sections.append(f'<section><table><caption>{table_caption}</caption><thead>{html_headers}</thead><tbody>{"".join(html_rows)}</tbody></table></section>')
    for note in spec.get("notes",[]): lines.append(r"\par\vspace{2pt}\begin{minipage}{0.8\linewidth}\footnotesize "+tex(note)+r"\end{minipage}")
    lines.append(r"\end{table}")
    horizontal=value["column_padding_pt"]*1.333; vertical=3.5*value["row_stretch"]*1.333
    text_width_css=f"width:{value['text_column_width_pt']*1.333:.1f}px;max-width:{value['text_column_width_pt']*1.333:.1f}px;white-space:normal;" if value.get("text_column_width_pt") else ""
    css=f"body{{font-family:Georgia,serif;margin:32px;color:#171717}}.caption,caption{{font-weight:600;margin-bottom:10px;text-align:left}}section{{margin-bottom:14px}}table{{border-collapse:collapse;font-variant-numeric:tabular-nums;font-size:{FONT_SIZES[value['font_size']]}px}}th,td{{padding:{vertical:.2f}px {horizontal:.2f}px;text-align:right}}th:first-child,td:first-child{{text-align:left;{text_width_css}}}thead{{border-top:2px solid;border-bottom:1px solid}}.super th,.groups th{{text-align:center;padding-top:3px;padding-bottom:3px}}.groups th:not(:first-child){{border-bottom:1px solid #777}}tbody{{border-bottom:2px solid}}.r1{{font-weight:700}}.r2{{text-decoration:underline}}.notes{{font-size:.86rem;margin-top:8px;max-width:900px}}"
    note=" ".join(html.escape(n) for n in spec.get("notes",[]))
    overall=f'<div class="caption">{html.escape(spec.get("caption",""))}</div>' if len(panels)>1 else ""
    page=f'<!doctype html><meta charset="utf-8"><style>{css}</style>{overall}{"".join(html_sections)}<div class="notes">{note}</div>'
    return "\n".join(lines)+"\n",page
def main():
    p=argparse.ArgumentParser(); p.add_argument("spec",type=Path); p.add_argument("--out-dir",type=Path,required=True); a=p.parse_args()
    spec=json.loads(a.spec.read_text()); a.out_dir.mkdir(parents=True,exist_ok=True); latex,page=render(spec)
    (a.out_dir/"table.tex").write_text(latex); (a.out_dir/"table.html").write_text(page); print(a.out_dir)
if __name__=="__main__": main()
