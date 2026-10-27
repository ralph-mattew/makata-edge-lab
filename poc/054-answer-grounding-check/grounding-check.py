#!/usr/bin/env python3
"""PoC 054 — answer-grounding post-check (OP-7). Forks 041: gate = answer-vs-chunk content-overlap fraction, tau-sweep."""
from __future__ import annotations
import argparse, json, math, os, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base/"007-embedding-retrieval-recall"/"results"/"raw"; P008 = _base/"008-absence-instruction-doc-qa"/"results"/"raw"; P014 = _base/"014-clause-aware-chunking"/"results"/"raw"
OUT = HERE/"results"; HARD=["Exclusivity","Non-Compete","Change Of Control"]; QP="task: search result | query: {t}"
STOP=set("a an the of to in on for and or is are be as by with at from this that these those shall will may any such other each party parties agreement contract hereof herein thereof pursuant section".split())
REF=re.compile(r"\b(not stated|not specified|not mentioned|not found|does not (?:contain|mention)|no (?:information|mention|such)|cannot|unable to|n/?a)\b",re.I)
AP=("Answer the question using ONLY the contract sections below. Be concise. If it is not in the sections, say \"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")
def tk(s): return re.findall(r"[a-z0-9]+",s.lower())
def cont(s): return [t for t in tk(s) if t not in STOP and len(t)>2]
def cos(a,b): return sum(x*y for x,y in zip(a,b))
def bm25(qt,docs,k1=1.5,b=0.75):
    N=len(docs); avg=sum(len(d) for d in docs)/max(N,1); df=Counter(t for d in docs for t in set(d)); idf={t:math.log(1+(N-df[t]+0.5)/(df[t]+0.5)) for t in df}; out=[]
    for d in docs:
        tf=Counter(d); out.append(sum(idf.get(t,0)*(tf[t]*(k1+1))/(tf[t]+k1*(1-b+b*len(d)/avg)) for t in qt))
    return out
def n01(xs):
    lo,hi=min(xs,default=0),max(xs,default=0); return [(x-lo)/(hi-lo) if hi>lo else 0.0 for x in xs]
def is_ref(a): return bool(REF.search(a)) or not a.strip()
def embed(url,texts,batch=16):
    out,i=[],0
    while i<len(texts):
        ch=[QP.format(t=t) for t in texts[i:i+batch]]; body=json.dumps({"input":ch}).encode()
        r=urllib.request.Request(url+"/v1/embeddings",data=body,headers={"Content-Type":"application/json"})
        try: out.extend(d["embedding"] for d in json.load(urllib.request.urlopen(r,timeout=600))["data"]); i+=batch
        except Exception:
            if batch==1: out.append([0.0]*(len(out[-1]) if out else 768)); i+=1
            else: batch=max(1,batch//2)
    return out
def qwen(url,p,n=64):
    body=json.dumps({"messages":[{"role":"user","content":p}],"n_predict":n,"temperature":0.0,"cache_prompt":True}).encode()
    r=urllib.request.Request(url+"/v1/chat/completions",data=body,headers={"Content-Type":"application/json"})
    for a in range(4):
        try: return json.load(urllib.request.urlopen(r,timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception: time.sleep(1.0*(a+1))
    return ""
def overlap_frac(ans, chunk):
    a=Counter(cont(ans));
    if not a: return 1.0  # empty/refusal handled separately
    c=set(cont(chunk)); return sum(v for t,v in a.items() if t in c)/sum(a.values())

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--emb-url",default="http://127.0.0.1:8090"); ap.add_argument("--qwen-url",default="http://127.0.0.1:8091"); ap.add_argument("--topk",type=int,default=3); ap.add_argument("--limit",type=int,default=0); a=ap.parse_args()
    rows=[json.loads(l) for l in open(P014/"chunks-page.jsonl")]; cvec=[json.loads(l)["vec"] for l in open(P014/"emb-page.jsonl")]; qv7={d["key"]:d["vec"] for d in map(json.loads,open(P014/"emb-queries.jsonl"))}
    byc=defaultdict(list)
    for i,r in enumerate(rows): byc[r["contract"]].append(i)
    dt=[tk(r["chunk"]) for r in rows]
    def top(qvec,qt,idxs):
        sem=[cos(qvec,cvec[i]) for i in idxs]; bm=n01(bm25(qt,[dt[i] for i in idxs])); h=[0.9*s+0.1*b for s,b in zip(n01(sem),bm)]
        return [idxs[j] for j in sorted(range(len(idxs)),key=lambda j:h[j],reverse=True)[:a.topk]]
    absent=[json.loads(l) for l in open(P008/"items.jsonl") if not json.loads(l)["answerable"] and json.loads(l)["category"] in HARD and json.loads(l)["contract"] in byc]
    answ=[it for it in (json.loads(l) for l in open(P007/"items.jsonl")) if it["category"] in HARD and it.get("gold_words") and it["contract"] in byc and it["qa_id"] in qv7]
    if a.limit: absent=absent[:a.limit]; answ=answ[:a.limit]
    print(f"absent {len(absent)} answerable {len(answ)}",flush=True); aq=embed(a.emb_url,[it["question"] for it in absent])
    def probe(it,qvec):
        tops=top(qvec,tk(it["question"]),byc[it["contract"]]); base=qwen(a.qwen_url,AP.format(ctx="\n\n".join(rows[j]["chunk"] for j in tops)[:6000],q=it["question"]))
        return {"base_refusal":is_ref(base),"overlap":round(overlap_frac(base,rows[tops[0]]["chunk"]),3)}
    A=[probe(it,q) for it,q in zip(absent,aq)]; N=[probe(it,qv7[it["qa_id"]]) for it in answ]; na,nn=len(A),len(N)
    base_car=100*sum(r["base_refusal"] for r in A)/na; base_loss=100*sum(r["base_refusal"] for r in N)/nn
    curve=[]
    for t in [round(x/100,2) for x in range(0,101,2)]:
        car=100*sum(r["base_refusal"] or r["overlap"]<t for r in A)/na; loss=100*sum(r["base_refusal"] or r["overlap"]<t for r in N)/nn
        curve.append({"tau":t,"CAR_gain":round(car-base_car,1),"loss":round(loss-base_loss,1)})
    feas=[c for c in curve if c["loss"]<=3.0]; best=max(feas,key=lambda c:c["CAR_gain"]) if feas else None
    h1=best is not None and best["CAR_gain"]>=5; h2=best is not None and best["loss"]<=3
    verdict="ADOPT" if (h1 and h2) else ("REJECT" if not any(c["CAR_gain"]>=5 and c["loss"]<=5 for c in curve) else "INCONCLUSIVE")
    res={"n_absent":na,"n_answerable":nn,"baseline_CAR":round(base_car,1),"baseline_answerable_refusal":round(base_loss,1),
         "best_feasible":best,"min_loss_at_+5CAR":min((c["loss"] for c in curve if c["CAR_gain"]>=5),default=None),
         "max_CARgain_at_loss<=3":max((c["CAR_gain"] for c in curve if c["loss"]<=3),default=0.0),
         "verdict":verdict,"ref":"041/043 dominated (max CAR gain @<=3pp loss = 0.0 / +27 loss)","curve":curve}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"grounding-check.json").write_text(json.dumps(res,indent=2))
    L=[f"baseline CAR {base_car:.1f} / answerable refusal {base_loss:.1f}",
       f"min loss to reach +5 CAR: {res['min_loss_at_+5CAR']}  | max CAR gain @loss<=3: {res['max_CARgain_at_loss<=3']}",
       f"best feasible (loss<=3): {best}", f"-> {verdict}"]
    print("\n".join(L)); (OUT/"comparison.txt").write_text("\n".join(L)+"\n")
if __name__=="__main__": main()
