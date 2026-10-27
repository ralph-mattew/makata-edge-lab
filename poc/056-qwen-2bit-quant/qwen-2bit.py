#!/usr/bin/env python3
"""PoC 056 — 2-bit (Q2_K) vs Q4_K_M Qwen (OP-8). Key-fact (464 typed-fact) + absent/answerable hard CAR, per server."""
from __future__ import annotations
import argparse, importlib.util, json, math, os, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent; _base=Path(os.environ.get("LAB_POC_ROOT",HERE.parent))
P007=_base/"007-embedding-retrieval-recall"/"results"/"raw"; P008=_base/"008-absence-instruction-doc-qa"/"results"/"raw"; P009=_base/"009-retrieval-depth-qwen"/"results"/"raw"; P014=_base/"014-clause-aware-chunking"/"results"/"raw"
FACTS=_base/"006-doc-qa-fm-gemma-qwen"/"facts.py"; OUT=HERE/"results"; HARD=["Exclusivity","Non-Compete","Change Of Control"]; QP="task: search result | query: {t}"
_s=importlib.util.spec_from_file_location("facts",FACTS); facts=importlib.util.module_from_spec(_s); _s.loader.exec_module(facts)
REF=re.compile(r"\b(not stated|not specified|not mentioned|not found|does not (?:contain|mention)|no (?:information|mention|such)|cannot|unable to|n/?a)\b",re.I)
AP=("Answer the question using ONLY the contract sections below. Be concise. If it is not in the sections, say \"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")
def tk(s): return re.findall(r"[a-z0-9]+",s.lower())
def cos(a,b): return sum(x*y for x,y in zip(a,b))
def bm25(qt,docs,k1=1.5,b=0.75):
    N=len(docs); avg=sum(len(d) for d in docs)/max(N,1); df=Counter(t for d in docs for t in set(d)); idf={t:math.log(1+(N-df[t]+0.5)/(df[t]+0.5)) for t in df}; o=[]
    for d in docs:
        tf=Counter(d); o.append(sum(idf.get(t,0)*(tf[t]*(k1+1))/(tf[t]+k1*(1-b+b*len(d)/avg)) for t in qt))
    return o
def n01(xs):
    lo,hi=min(xs,default=0),max(xs,default=0); return [(x-lo)/(hi-lo) if hi>lo else 0.0 for x in xs]
def is_ref(a): return bool(REF.search(a)) or not a.strip()
def nb(v): return v if isinstance(v,bool) else (str(v).lower()=="true")
def embed(url,texts,batch=16):
    o,i=[],0
    while i<len(texts):
        ch=[QP.format(t=t) for t in texts[i:i+batch]]; body=json.dumps({"input":ch}).encode(); r=urllib.request.Request(url+"/v1/embeddings",data=body,headers={"Content-Type":"application/json"})
        try: o.extend(d["embedding"] for d in json.load(urllib.request.urlopen(r,timeout=600))["data"]); i+=batch
        except Exception:
            if batch==1: o.append([0.0]*(len(o[-1]) if o else 768)); i+=1
            else: batch=max(1,batch//2)
    return o
def qwen(url,p,n=160):
    body=json.dumps({"messages":[{"role":"user","content":p}],"n_predict":n,"temperature":0.0,"cache_prompt":True}).encode(); r=urllib.request.Request(url+"/v1/chat/completions",data=body,headers={"Content-Type":"application/json"})
    for a in range(4):
        try: return json.load(urllib.request.urlopen(r,timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception: time.sleep(1.0*(a+1))
    return ""

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--emb-url",default="http://127.0.0.1:8090"); ap.add_argument("--q4-url",default="http://127.0.0.1:8091"); ap.add_argument("--q2-url",default="http://127.0.0.1:8092"); ap.add_argument("--limit",type=int,default=0); a=ap.parse_args()
    rows=[json.loads(l) for l in open(P014/"chunks-page.jsonl")]; cvec=[json.loads(l)["vec"] for l in open(P014/"emb-page.jsonl")]; qv={d["key"]:d["vec"] for d in map(json.loads,open(P014/"emb-queries.jsonl"))}
    byc=defaultdict(list)
    for i,r in enumerate(rows): byc[r["contract"]].append(i)
    dt=[tk(r["chunk"]) for r in rows]
    kf=[it for it in (json.loads(l) for l in open(P009/"items.jsonl")) if it.get("key_facts") and nb(it["answerable"]) and it["contract"] in byc and it["qa_id"] in qv]
    absent=[json.loads(l) for l in open(P008/"items.jsonl") if not json.loads(l)["answerable"] and json.loads(l)["category"] in HARD and json.loads(l)["contract"] in byc]
    if a.limit: kf=kf[:a.limit]; absent=absent[:a.limit]
    aq=embed(a.emb_url,[it["question"] for it in absent])
    def top(qvec,qt,idxs,k=3):
        sem=[cos(qvec,cvec[i]) for i in idxs]; bm=n01(bm25(qt,[dt[i] for i in idxs])); h=[0.9*s+0.1*b for s,b in zip(n01(sem),bm)]
        return [idxs[j] for j in sorted(range(len(idxs)),key=lambda j:h[j],reverse=True)[:k]]
    def evalu(url):
        pc=defaultdict(list)
        for it in kf:
            ctx="\n\n".join(rows[c]["chunk"] for c in top(qv[it["qa_id"]],tk(it["question"]),byc[it["contract"]]))[:6000]
            ans=qwen(url,AP.format(ctx=ctx,q=it["question"])); gold={tuple(f) for f in it["key_facts"]}
            pc[it["contract"]].append(bool(gold & {tuple(f) for f in facts.key_facts(it["key_fact_kind"],ans)}))
        flat=[h for g in pc.values() for h in g]; keyfact=round(100*sum(flat)/len(flat),1)
        car=0
        for it,q in zip(absent,aq):
            ctx="\n\n".join(rows[c]["chunk"] for c in top(q,tk(it["question"]),byc[it["contract"]]))[:6000]
            car+=is_ref(qwen(url,AP.format(ctx=ctx,q=it["question"])))
        return {"key_fact":keyfact,"absent_CAR":round(100*car/len(absent),1)}
    def health(u):
        try: return b"ok" in urllib.request.urlopen(u+"/health",timeout=3).read()
        except Exception: return False
    res={"n_keyfact":len(kf),"n_absent":len(absent)}
    res["Q4"]=evalu(a.q4_url)
    res["Q2_K"]=evalu(a.q2_url) if health(a.q2_url) else {"error":"Q2_K server not up"}
    if "error" not in res["Q2_K"]:
        res["delta_key_fact"]=round(res["Q2_K"]["key_fact"]-res["Q4"]["key_fact"],1)
        res["delta_absent_CAR"]=round(res["Q2_K"]["absent_CAR"]-res["Q4"]["absent_CAR"],1)
        h1=res["delta_key_fact"]>=-3; h3=res["delta_absent_CAR"]>=-3
        res["verdict"]=("ADOPT" if (h1 and h3) else ("REJECT" if res["delta_key_fact"]<-6 else "INCONCLUSIVE"))
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"qwen-2bit.json").write_text(json.dumps(res,indent=2))
    print(json.dumps(res,indent=2)); (OUT/"comparison.txt").write_text(json.dumps(res,indent=2)+"\n")
if __name__=="__main__": main()
