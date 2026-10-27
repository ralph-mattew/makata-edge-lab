#!/usr/bin/env python3
"""PoC 058 — Qwen-1.5B as a length-limited LLM reranker (OP-1). Hybrid top-10 -> Qwen P(YES) rerank -> recall@3 (hard)."""
from __future__ import annotations
import argparse, json, math, os, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent; _base=Path(os.environ.get("LAB_POC_ROOT",HERE.parent))
P007=_base/"007-embedding-retrieval-recall"/"results"/"raw"; P014=_base/"014-clause-aware-chunking"/"results"/"raw"
OUT=HERE/"results"; HARD=["Exclusivity","Non-Compete","Change Of Control"]
GATE=("Does the following contract passage contain a {cat} clause? Answer YES or NO only.\n\nPASSAGE:\n{ctx}\n\nANSWER (YES/NO):")
def tk(s): return re.findall(r"[a-z0-9]+",s.lower())
def cos(a,b): return sum(x*y for x,y in zip(a,b))
def bm25(qt,docs,k1=1.5,b=0.75):
    N=len(docs); avg=sum(len(d) for d in docs)/max(N,1); df=Counter(t for d in docs for t in set(d)); idf={t:math.log(1+(N-df[t]+0.5)/(df[t]+0.5)) for t in df}; o=[]
    for d in docs:
        tf=Counter(d); o.append(sum(idf.get(t,0)*(tf[t]*(k1+1))/(tf[t]+k1*(1-b+b*len(d)/avg)) for t in qt))
    return o
def n01(xs):
    lo,hi=min(xs,default=0),max(xs,default=0); return [(x-lo)/(hi-lo) if hi>lo else 0.0 for x in xs]
def covers(sp,g,frac=0.5):
    if not sp or not g: return False
    s0,s1=sp; g0,g1=g; return max(0,min(s1,g1)-max(s0,g0)+1)>=frac*(g1-g0+1)
def pyes(url,prompt):
    body=json.dumps({"messages":[{"role":"user","content":prompt}],"max_tokens":1,"temperature":0.0,"logprobs":True,"top_logprobs":20,"cache_prompt":True}).encode()
    r=urllib.request.Request(url+"/v1/chat/completions",data=body,headers={"Content-Type":"application/json"})
    for a in range(4):
        try:
            d=json.load(urllib.request.urlopen(r,timeout=180))["choices"][0]; lp=(d.get("logprobs") or {}).get("content") or []; y=nn=0.0
            if lp:
                for t in lp[0].get("top_logprobs",[]):
                    tok=t["token"].strip().lower(); p=math.exp(t["logprob"])
                    if tok.startswith("y"): y+=p
                    elif tok.startswith("n"): nn+=p
            return y/(y+nn) if y+nn>0 else (1.0 if d["message"]["content"].strip().upper().startswith("Y") else 0.0)
        except Exception: time.sleep(1.0*(a+1))
    return 0.5

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--qwen-url",default="http://127.0.0.1:8091"); ap.add_argument("--pool",type=int,default=10); ap.add_argument("--topk",type=int,default=3); ap.add_argument("--win",type=int,default=600); ap.add_argument("--limit",type=int,default=0); a=ap.parse_args()
    rows=[json.loads(l) for l in open(P014/"chunks-page.jsonl")]; cvec=[json.loads(l)["vec"] for l in open(P014/"emb-page.jsonl")]; qv={d["key"]:d["vec"] for d in map(json.loads,open(P014/"emb-queries.jsonl"))}
    byc=defaultdict(list)
    for i,r in enumerate(rows): byc[r["contract"]].append(i)
    dt=[tk(r["chunk"]) for r in rows]; spans=[tuple(r["span"]) if r.get("span") else None for r in rows]
    items=[it for it in (json.loads(l) for l in open(P007/"items.jsonl")) if it["category"] in HARD and it.get("gold_words") and it["contract"] in byc and it["qa_id"] in qv]
    if a.limit: items=items[:a.limit]
    print(f"{len(items)} hard items; Qwen rerank pool={a.pool}",flush=True)
    def hybrid(it):
        idxs=byc[it["contract"]]; q=qv[it["qa_id"]]; qt=tk(it["question"]); sem=[cos(q,cvec[i]) for i in idxs]; bm=n01(bm25(qt,[dt[i] for i in idxs])); h=[0.9*s+0.1*b for s,b in zip(n01(sem),bm)]
        return [idxs[j] for j in sorted(range(len(idxs)),key=lambda j:h[j],reverse=True)]
    base_cat=defaultdict(list); rr_cat=defaultdict(list)
    for it in items:
        order=hybrid(it); gold=tuple(it["gold_words"])
        base_cat[it["category"]].append(any(covers(spans[j],gold) for j in order[:a.topk]))
        pool=order[:a.pool]; sc=[pyes(a.qwen_url,GATE.format(cat=it["category"],ctx=rows[j]["chunk"][:a.win])) for j in pool]
        rer=[pool[i] for i in sorted(range(len(pool)),key=lambda i:sc[i],reverse=True)]
        rr_cat[it["category"]].append(any(covers(spans[j],gold) for j in rer[:a.topk]))
    def hm(d): c={k:100*sum(v)/len(v) for k,v in d.items() if v}; return round(sum(c.values())/len(c),1),{k:round(x,1) for k,x in c.items()}
    b_hm,b_c=hm(base_cat); r_hm,r_c=hm(rr_cat)
    res={"n":len(items),"baseline_top3":{"hard_mean":b_hm,"per_cat":b_c},"qwen_reranked_top3":{"hard_mean":r_hm,"per_cat":r_c},
         "delta":round(r_hm-b_hm,1),"ref":"027 cross-encoder rerank REJECTED (NC 25->8-15); hard-cat retrieval solved by 053 (54.0)"}
    per_cat_reg=any(r_c.get(k,0)<b_c.get(k,0)-0.1 for k in HARD)
    res["verdict"]=("ADOPT" if (res["delta"]>=5 and not per_cat_reg) else ("REJECT" if res["delta"]<2 or per_cat_reg else "INCONCLUSIVE"))
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"qwen-rerank.json").write_text(json.dumps(res,indent=2))
    L=[f"baseline top-3 hard-mean {b_hm}  {b_c}", f"Qwen-reranked  hard-mean {r_hm}  {r_c}", f"Δ {res['delta']:+.1f}  -> {res['verdict']}"]
    print("\n".join(L)); (OUT/"comparison.txt").write_text("\n".join(L)+"\n")
if __name__=="__main__": main()
