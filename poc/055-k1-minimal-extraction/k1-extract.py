#!/usr/bin/env python3
"""PoC 055 — k=1 vs k=3 minimal extraction (OP-2). Forks 047: cosine + Qwen-copy arms x depth {1,3}, span-F1 on 300 hard items."""
from __future__ import annotations
import argparse, json, math, os, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent; _base=Path(os.environ.get("LAB_POC_ROOT",HERE.parent))
P007=_base/"007-embedding-retrieval-recall"/"results"/"raw"; P014=_base/"014-clause-aware-chunking"/"results"/"raw"; P016=_base/"016-crossref-decomposition"/"results"/"raw"
OUT=HERE/"results"; HARD=["Exclusivity","Non-Compete","Change Of Control"]; DOC="title: none | text: {t}"
STOP=set("a an the of to in on for and or is are be as by with at from this that these those shall will may any such other each party parties agreement contract hereof herein thereof pursuant section".split())
def tk(s): return re.findall(r"[a-z0-9]+",s.lower())
def cont(s): return [t for t in tk(s) if t not in STOP and len(t)>2]
def cos(a,b): return sum(x*y for x,y in zip(a,b))
def bm25(qt,docs,k1=1.5,b=0.75):
    N=len(docs); avg=sum(len(d) for d in docs)/max(N,1); df=Counter(t for d in docs for t in set(d)); idf={t:math.log(1+(N-df[t]+0.5)/(df[t]+0.5)) for t in df}; o=[]
    for d in docs:
        tf=Counter(d); o.append(sum(idf.get(t,0)*(tf[t]*(k1+1))/(tf[t]+k1*(1-b+b*len(d)/avg)) for t in qt))
    return o
def n01(xs):
    lo,hi=min(xs,default=0),max(xs,default=0); return [(x-lo)/(hi-lo) if hi>lo else 0.0 for x in xs]
def ssplit(t,mn=3,mx=80):
    o=[]
    for p in re.split(r"(?<=[.;:!?])\s+|\n+",t):
        w=p.strip().split()
        if len(w)<mn: continue
        for i in range(0,len(w),mx): o.append(" ".join(w[i:i+mx]))
    return o
def f1(ans,gold):
    a,g=Counter(cont(ans)),Counter(cont(gold))
    if not a or not g: return 0.0
    ov=sum((a&g).values()); pr=ov/sum(a.values()); rc=ov/sum(g.values()); return 2*pr*rc/(pr+rc) if (pr+rc) else 0.0
def embed(url,texts,batch=16):
    o,i=[],0
    while i<len(texts):
        ch=[DOC.format(t=t) for t in texts[i:i+batch]]; body=json.dumps({"input":ch}).encode(); r=urllib.request.Request(url+"/v1/embeddings",data=body,headers={"Content-Type":"application/json"})
        try: o.extend(d["embedding"] for d in json.load(urllib.request.urlopen(r,timeout=600))["data"]); i+=batch
        except Exception:
            if batch==1: o.append([0.0]*(len(o[-1]) if o else 768)); i+=1
            else: batch=max(1,batch//2)
    return o
COPY=("Copy the single sentence from the contract sections below that best answers the question. Output that sentence verbatim and nothing else.\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nSENTENCE:")
def qwen(url,p,n=120):
    body=json.dumps({"messages":[{"role":"user","content":p}],"n_predict":n,"temperature":0.0,"cache_prompt":True}).encode(); r=urllib.request.Request(url+"/v1/chat/completions",data=body,headers={"Content-Type":"application/json"})
    for a in range(4):
        try: return json.load(urllib.request.urlopen(r,timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception: time.sleep(1.0*(a+1))
    return ""
def boot(pc,n=10000,seed=0):
    random.seed(seed); g=list(pc.values()); bo=[]
    for _ in range(n):
        xs=[v for gr in (random.choice(g) for _ in g) for v in gr]; bo.append(100*sum(xs)/len(xs) if xs else 0.0)
    bo.sort(); return bo[int(.025*n)],bo[int(.975*n)]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--emb-url",default="http://127.0.0.1:8090"); ap.add_argument("--qwen-url",default="http://127.0.0.1:8091"); ap.add_argument("--window",type=int,default=3); ap.add_argument("--limit",type=int,default=0); a=ap.parse_args()
    rows=[json.loads(l) for l in open(P014/"chunks-page.jsonl")]; cvec=[json.loads(l)["vec"] for l in open(P014/"emb-page.jsonl")]
    sub={d["key"]:d["vec"] for d in map(json.loads,open(P016/"emb-subqueries.jsonl"))}; tmpl=json.loads((P016/"decomp-templates.json").read_text())
    contr={c["contract"]:c for c in map(json.loads,open(P007/"contracts.jsonl"))}; byc=defaultdict(list)
    for i,r in enumerate(rows): byc[r["contract"]].append(i)
    dt=[tk(r["chunk"]) for r in rows]
    items=[json.loads(l) for l in open(P007/"items.jsonl") if json.loads(l)["category"] in HARD]
    work=[]
    for it in items:
        c=contr.get(it["contract"]); g=it.get("gold_words"); idxs=byc.get(it["contract"],[])
        if not c or not g or not idxs: continue
        if not all(f'{it["qa_id"]}#{k}' in sub for k in range(len(tmpl.get(it["category"],[])))): continue
        gold=" ".join((" ".join(c.get("pages",[]) or [])).split()[g[0]:g[1]+1])
        if cont(gold): work.append((it,gold))
    if a.limit: work=work[:a.limit]
    print(f"{len(work)} hard items; depth {{1,3}} x arms {{cosine,copy}}",flush=True)
    def decomp(it,K):
        idxs=byc[it["contract"]]; best={}
        for k,s in enumerate(tmpl[it["category"]]):
            qv=sub[f'{it["qa_id"]}#{k}']; sem=[cos(qv,cvec[i]) for i in idxs]; bm=n01(bm25(tk(s),[dt[i] for i in idxs])); h=[0.9*x+0.1*y for x,y in zip(n01(sem),bm)]
            for j in sorted(range(len(idxs)),key=lambda j:h[j],reverse=True)[:K]: best[j]=max(best.get(j,-1e9),h[j])
        return [idxs[j] for j in sorted(best,key=lambda j:best[j],reverse=True)[:K]]
    retr={K:{it["qa_id"]:decomp(it,K) for it,_ in work} for K in (1,3)}
    alls=list(dict.fromkeys(s for K in (1,3) for it,_ in work for ci in retr[K][it["qa_id"]] for s in ssplit(rows[ci]["chunk"])))
    print(f"embedding {len(alls)} sentences",flush=True); sv=dict(zip(alls,embed(a.emb_url,alls)))
    res={}
    for K in (1,3):
        for arm in ("cosine","copy"):
            pc=defaultdict(list); cat=defaultdict(list)
            for it,gold in work:
                chunks=[rows[ci]["chunk"] for ci in retr[K][it["qa_id"]]]
                if arm=="cosine":
                    subs=[sub[f'{it["qa_id"]}#{k}'] for k in range(len(tmpl[it["category"]]))]; sents=[s for ch in chunks for s in ssplit(ch)]
                    if sents:
                        sc=[max(cos(sv[s],q) for q in subs) for s in sents]; bi=max(range(len(sents)),key=lambda i:sc[i]); lo=max(0,bi-(a.window-1)//2); hi=min(len(sents),lo+a.window); ans=" ".join(sents[lo:hi])
                    else: ans=""
                else:
                    ans=qwen(a.qwen_url,COPY.format(ctx="\n\n".join(chunks)[:6000],q=it["question"]))
                v=f1(ans,gold); cat[it["category"]].append(v); pc[it["contract"]].append(v)
            cats={c:round(100*sum(cat[c])/len(cat[c]),1) for c in HARD if cat[c]}
            res[f"{arm}_k{K}"]={"hard_mean":round(sum(cats.values())/len(cats),1),"per_cat":cats,"ci":[round(x,1) for x in boot(pc)]}
    bestk3=max(res["cosine_k3"]["hard_mean"],res["copy_k3"]["hard_mean"]); bestk1=max(res["cosine_k1"]["hard_mean"],res["copy_k1"]["hard_mean"])
    res["best_k1_minus_best_k3"]=round(bestk1-bestk3,1); res["verdict"]=("ADOPT k=1" if res["best_k1_minus_best_k3"]>=3 else ("REJECT k=1" if res["best_k1_minus_best_k3"]<0 else "INCONCLUSIVE"))
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"k1-extract.json").write_text(json.dumps(res,indent=2))
    L=[f"{k:11} {res[k]['hard_mean']:5.1f}  {res[k]['per_cat']}" for k in ("cosine_k1","cosine_k3","copy_k1","copy_k3")]
    L.append(f"best_k1 - best_k3 = {res['best_k1_minus_best_k3']:+.1f}  -> {res['verdict']}")
    print("\n".join(L)); (OUT/"comparison.txt").write_text("\n".join(L)+"\n")
if __name__=="__main__": main()
