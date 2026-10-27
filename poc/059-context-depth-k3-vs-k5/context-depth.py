#!/usr/bin/env python3
"""PoC 059 — generation context depth k=3 vs k=5 (OP-2). Key-fact on 464 typed-fact items."""
from __future__ import annotations
import argparse, importlib.util, json, math, os, random, re, time, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
_base = Path(os.environ.get("LAB_POC_ROOT", HERE.parent))
P007 = _base / "007-embedding-retrieval-recall" / "results" / "raw"
P009 = _base / "009-retrieval-depth-qwen" / "results" / "raw"
P014 = _base / "014-clause-aware-chunking" / "results" / "raw"
FACTS = _base / "006-doc-qa-fm-gemma-qwen" / "facts.py"
OUT = HERE / "results"
_s = importlib.util.spec_from_file_location("facts", FACTS); facts = importlib.util.module_from_spec(_s); _s.loader.exec_module(facts)
REF = re.compile(r"\b(not stated|not specified|not mentioned|not found|does not (?:contain|mention)|no (?:information|mention|such)|cannot|unable to|n/?a)\b", re.I)
PROMPT = ("Answer the question using ONLY the contract sections below. Be concise. If it is not in the "
          "sections, say \"not stated\".\n\nSECTIONS:\n{ctx}\n\nQUESTION: {q}\nANSWER:")
def cos(a,b): return sum(x*y for x,y in zip(a,b))
def tk(s): return re.findall(r"[a-z0-9]+", s.lower())
def bm25(qt,docs,k1=1.5,b=0.75):
    N=len(docs); avg=sum(len(d) for d in docs)/max(N,1); df=Counter(t for d in docs for t in set(d))
    idf={t:math.log(1+(N-df[t]+0.5)/(df[t]+0.5)) for t in df}; out=[]
    for d in docs:
        tf=Counter(d); out.append(sum(idf.get(t,0)*(tf[t]*(k1+1))/(tf[t]+k1*(1-b+b*len(d)/avg)) for t in qt))
    return out
def n01(xs):
    lo,hi=min(xs,default=0),max(xs,default=0); return [(x-lo)/(hi-lo) if hi>lo else 0.0 for x in xs]
def is_ref(a): return bool(REF.search(a)) or not a.strip()
def nb(v): return v if isinstance(v,bool) else (str(v).lower()=="true")
def qwen(url,p,n=160):
    body=json.dumps({"messages":[{"role":"user","content":p}],"n_predict":n,"temperature":0.0,"cache_prompt":True}).encode()
    r=urllib.request.Request(url+"/v1/chat/completions",data=body,headers={"Content-Type":"application/json"})
    for a in range(4):
        try: return json.load(urllib.request.urlopen(r,timeout=180))["choices"][0]["message"]["content"].strip()
        except Exception: time.sleep(1.0*(a+1))
    return ""
def boot(pc,n=10000,seed=0):
    random.seed(seed); g=list(pc.values()); bo=[]
    for _ in range(n):
        xs=[v for grp in (random.choice(g) for _ in g) for v in grp]; bo.append(100*sum(xs)/len(xs) if xs else 0.0)
    bo.sort(); return bo[int(.025*n)],bo[int(.975*n)]

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--qwen-url",default="http://127.0.0.1:8091"); ap.add_argument("--limit",type=int,default=0); a=ap.parse_args()
    rows=[json.loads(l) for l in open(P014/"chunks-page.jsonl")]; cvec=[json.loads(l)["vec"] for l in open(P014/"emb-page.jsonl")]
    qv={d["key"]:d["vec"] for d in map(json.loads,open(P014/"emb-queries.jsonl"))}
    byc=defaultdict(list)
    for i,r in enumerate(rows): byc[r["contract"]].append(i)
    dt=[tk(r["chunk"]) for r in rows]
    work=[it for it in (json.loads(l) for l in open(P009/"items.jsonl")) if it.get("key_facts") and nb(it["answerable"]) and it["contract"] in byc and it["qa_id"] in qv]
    if a.limit: work=work[:a.limit]
    print(f"{len(work)} typed-fact items; k=3 vs k=5",flush=True)
    def topk(it,k):
        idxs=byc[it["contract"]]; q=qv[it["qa_id"]]; qt=tk(it["question"])
        sem=[cos(q,cvec[i]) for i in idxs]; bm=n01(bm25(qt,[dt[i] for i in idxs]))
        h=[0.9*s+0.1*b for s,b in zip(n01(sem),bm)]
        return [idxs[j] for j in sorted(range(len(idxs)),key=lambda j:h[j],reverse=True)[:k]]
    def run(k):
        pc,ref=defaultdict(list),[]
        for it in work:
            ctx="\n\n".join(rows[c]["chunk"] for c in topk(it,k))[:6000]
            ans=qwen(a.qwen_url,PROMPT.format(ctx=ctx,q=it["question"]))
            gold={tuple(f) for f in it["key_facts"]}; hit=bool(gold & {tuple(f) for f in facts.key_facts(it["key_fact_kind"],ans)})
            pc[it["contract"]].append(hit); ref.append(is_ref(ans))
        flat=[h for g in pc.values() for h in g]
        return {"key_fact":round(100*sum(flat)/len(flat),1),"ci":[round(x,1) for x in boot(pc)],"refusal":round(100*sum(ref)/len(ref),1)}
    k3=run(3); k5=run(5)
    res={"n":len(work),"k3":k3,"k5":k5,"delta_k5_minus_k3":round(k5["key_fact"]-k3["key_fact"],1)}
    res["verdict"]=("CONFIRM k=3 (k=5 degrades)" if res["delta_k5_minus_k3"]<=-5 else ("REFUTE dilution (k5~k3)" if abs(res["delta_k5_minus_k3"])<=2 else "INCONCLUSIVE"))
    OUT.mkdir(parents=True,exist_ok=True); (OUT/"context-depth.json").write_text(json.dumps(res,indent=2))
    L=[f"k=3 key-fact {k3['key_fact']} (CI {k3['ci']}) refusal {k3['refusal']}",
       f"k=5 key-fact {k5['key_fact']} (CI {k5['ci']}) refusal {k5['refusal']}",
       f"Δ(k5-k3) {res['delta_k5_minus_k3']:+.1f}  -> {res['verdict']}"]
    print("\n".join(L)); (OUT/"comparison.txt").write_text("\n".join(L)+"\n")
if __name__=="__main__": main()
