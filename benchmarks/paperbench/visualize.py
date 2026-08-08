#!/usr/bin/env python3
"""Create a repository-ready reference-vs-generated comparison dashboard."""
from __future__ import annotations
import json, textwrap
from pathlib import Path
import matplotlib.pyplot as plt
from PIL import Image

ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent; OUT=ROOT/"output/paperbench"
def main():
    metrics=json.loads((OUT/"summary.json").read_text()); n=len(metrics)
    fig=plt.figure(figsize=(15,4.8*n),layout="constrained"); gs=fig.add_gridspec(n,3,width_ratios=[1.35,1.35,1.0])
    dims=[("numeric_recall","Numeric recall"),("numeric_precision","Numeric precision"),("cell_recall","Cell recall"),("header_recall","Header recall")]
    for i,m in enumerate(metrics):
        case=HERE/"cases"/m["id"]; imgs=[Image.open(case/"y_reference.png"),Image.open(OUT/m["id"]/"y_prime.png")]
        for j,(im,title) in enumerate(zip(imgs,["Published reference y","PaperTable output y′"])):
            ax=fig.add_subplot(gs[i,j]); ax.imshow(im); ax.axis("off"); ax.set_title((m["id"]+"\n" if j==0 else "")+title,fontsize=12,fontweight="bold")
        ax=fig.add_subplot(gs[i,2]); vals=[m[k] for k,_ in dims]; labels=[v for _,v in dims]; y0=list(range(4))
        ax.barh(y0,vals,color="#0B8F78",height=.55,label="Objective score")
        pilot=m.get("pilot_rubric",{}); adims=[("typography","Typography"),("visual_hierarchy","Hierarchy"),("readability","Readability"),("claim_salience","Claim salience"),("overall_aesthetics","Overall aesthetics")]
        if pilot:
            for k,(key,label) in enumerate(adims,start=5):
                ax.scatter(pilot["reference"][key]/5,k,color="#4C78A8",s=48,marker="o",label="Reference pilot rubric" if k==5 else None)
                ax.scatter(pilot["generated"][key]/5,k,color="#F58518",s=48,marker="D",label="Generated pilot rubric" if k==5 else None)
        else:
            ax.text(.5,7,"N/A\nunrated",ha="center",va="center",fontsize=11,color="#666666")
        ax.set_yticks(y0+list(range(5,10)),labels+[x[1] for x in adims]); ax.set_xlim(0,1.05); ax.invert_yaxis(); ax.grid(axis="x",alpha=.2)
        for y,v in zip(y0,vals): ax.text(v+.015,y,f"{v:.2f}",va="center",fontsize=8)
        ax.axhline(4.5,color="#AAAAAA",lw=.8); ax.set_title("Fidelity + visual rubric status",fontsize=11,fontweight="bold"); ax.legend(loc="lower right",fontsize=7,frameon=False)
        rubric_note="Pilot visual rubric is model-scored, not human-validated." if pilot else "Visual rubric is unrated; missing ratings are not scored as zero."
        ax.text(0,-.18,rubric_note,transform=ax.transAxes,color="#8A3B12",fontsize=8)
    fig.suptitle("PaperBench mini: published tables vs code-generated tables",fontsize=18,fontweight="bold")
    out=OUT/"comparison.png"; fig.savefig(out,dpi=180,bbox_inches="tight",facecolor="white")
    public=ROOT/"docs/assets/paperbench-comparison.png"; public.parent.mkdir(parents=True,exist_ok=True); fig.savefig(public,dpi=180,bbox_inches="tight",facecolor="white")
    print(out); print(public)
if __name__=="__main__": main()
