#!/usr/bin/env python3
"""Collect reproducible table cases from official NeurIPS proceedings PDFs."""
from __future__ import annotations
import argparse, hashlib, io, json, random, re, urllib.request
from html.parser import HTMLParser
from pathlib import Path

UA={"User-Agent":"PaperTable research benchmark/0.1"}
class Links(HTMLParser):
    def __init__(self): super().__init__(); self.hrefs=[]
    def handle_starttag(self,tag,attrs):
        if tag=="a":
            d=dict(attrs)
            if "href" in d: self.hrefs.append(d["href"])
def get(url): return urllib.request.urlopen(urllib.request.Request(url,headers=UA),timeout=45).read()
def sha(data): return hashlib.sha256(data).hexdigest()
def discover(year):
    base=f"https://proceedings.neurips.cc/paper_files/paper/{year}"
    p=Links(); p.feed(get(f"https://papers.nips.cc/paper/{year}").decode("utf-8","ignore"))
    urls=[]
    for h in p.hrefs:
        if "-Abstract-" in h and h.endswith(".html"):
            h=h.replace("/hash/","/file/").replace("-Abstract-","-Paper-").removesuffix(".html")+".pdf"
            urls.append(h if h.startswith("http") else "https://proceedings.neurips.cc"+h)
    return sorted(set(urls))
def main():
    p=argparse.ArgumentParser(); p.add_argument("--year",type=int,default=2024); p.add_argument("--papers",type=int,default=50); p.add_argument("--max-tables",type=int,default=200); p.add_argument("--seed",type=int,default=7); p.add_argument("--out",type=Path,default=Path(__file__).with_name("index.jsonl")); a=p.parse_args()
    try: import pypdfium2
    except ImportError: raise SystemExit("Install dependencies with: pip install pypdfium2 Pillow")
    urls=discover(a.year); random.Random(a.seed).shuffle(urls); urls=urls[:a.papers]
    cache=Path(__file__).with_name("cache")/str(a.year); material=Path(__file__).with_name("materialized")/str(a.year); cache.mkdir(parents=True,exist_ok=True); material.mkdir(parents=True,exist_ok=True)
    cases=[]
    for pi,url in enumerate(urls,1):
        paper_id=url.rsplit("/",1)[-1].split("-Paper-")[0]; pdf_path=cache/f"{paper_id}.pdf"
        try:
            data=pdf_path.read_bytes() if pdf_path.exists() else get(url)
            if not pdf_path.exists(): pdf_path.write_bytes(data)
            pdf=pypdfium2.PdfDocument(data)
            for page_no,page in enumerate(pdf,1):
                textpage=page.get_textpage(); search=textpage.search("Table ",match_case=False); found=[]
                while True:
                    hit=search.get_next()
                    if hit is None: break
                    index,count=hit; prefix=textpage.get_text_range(max(0,index-3),min(3,index))
                    caption=textpage.get_text_range(index,min(500,textpage.count_chars()-index)).split("\n",1)[0].strip()
                    if not re.match(r"Table\s+[A-Z]?\d+",caption,re.I) or (index>0 and "\n" not in prefix and "\r" not in prefix): continue
                    boxes=[textpage.get_charbox(j) for j in range(index,index+min(len(caption),count+200)) if j<textpage.count_chars()]
                    if not boxes: continue
                    left=min(b[0] for b in boxes); bottom=min(b[1] for b in boxes); right=max(b[2] for b in boxes); top=max(b[3] for b in boxes)
                    found.append((caption,(left,bottom,right,top)))
                if found:
                    rendered=page.render(scale=2).to_pil(); page_w,page_h=page.get_size()
                    for ti,(caption,cb) in enumerate(found,1):
                        # NeurIPS convention places the caption above the table; retain a generous code-verifiable region.
                        bbox=[0,max(18,cb[1]-300),page_w,min(page_h,cb[3]+5)]
                        pixel=(int(bbox[0]*2),int((page_h-bbox[3])*2),int(bbox[2]*2),int((page_h-bbox[1])*2))
                        cid=f"n{a.year}-{paper_id[:10]}-p{page_no}-t{ti}"; crop=rendered.crop(pixel); crop_path=material/f"{cid}.png"; crop.save(crop_path)
                        region_text=textpage.get_text_bounded(*bbox)
                        cases.append({"id":cid,"year":a.year,"paper_url":url,"paper_sha256":sha(data),"page":page_no,"bbox_pdf_points":list(map(lambda x:round(float(x),2),bbox)),"caption":caption,"region_text":region_text,"region_text_sha256":sha(region_text.encode()),"crop_path":str(crop_path.relative_to(Path(__file__).parents[2])),"crop_sha256":sha(crop_path.read_bytes())})
                        if len(cases)>=a.max_tables: break
                    if len(cases)>=a.max_tables: break
        except Exception as e: print(f"skip {url}: {e}")
        print(f"[{pi}/{len(urls)}] tables={len(cases)}")
        if len(cases)>=a.max_tables: break
    a.out.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in cases)); print(f"wrote {len(cases)} cases to {a.out}")
if __name__=="__main__": main()
