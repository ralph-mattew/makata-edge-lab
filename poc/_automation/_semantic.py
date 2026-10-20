"""Semantic (embedding) discovery arm for Stage 1.

Keyword search only finds papers that use the lab's own vocabulary. This arm
embeds the lab's *open problems* and the abstracts of recent arXiv papers, then
keeps the papers closest in meaning — so work that's relevant but worded
differently (an adjacent-field compression trick, say) still surfaces.

Optional and lazily loaded: disabled in config, or missing `sentence-transformers`,
returns [] with a note rather than failing the scan.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, List, Optional


def problem_statements(config: Dict) -> List[str]:
    """The lab's open problems to match against. Explicit `semantic.problems`
    wins; otherwise derive a couple from the system-context baseline."""
    sem = config.get("sources", {}).get("semantic", {})
    probs = list(sem.get("problems") or [])
    if probs:
        return probs
    sc = config.get("system_context", {})
    return [
        f"Reduce on-device RAG memory below the {sc.get('embedding_model')} footprint "
        f"on a {sc.get('ram_budget')} device without losing retrieval recall",
        f"Improve retrieval recall@3 above {sc.get('current_recall')}% under mobile "
        f"memory and thermal constraints",
    ]


def default_embedder(model_name: str) -> Callable[[List[str]], "object"]:
    """Return an embed(texts)->ndarray fn backed by sentence-transformers
    (L2-normalized, so a dot product is cosine similarity)."""
    from sentence_transformers import SentenceTransformer
    import numpy as np
    model = SentenceTransformer(model_name)

    def embed(texts: List[str]):
        return np.asarray(model.encode(texts, normalize_embeddings=True))

    return embed


def rank_by_similarity(papers: List[Dict], problems: List[str], embed_fn,
                       min_similarity: float, top_k: int,
                       existing_titles: Optional[set] = None) -> List[Dict]:
    """Pure ranking: keep papers whose max cosine similarity to any problem is
    >= min_similarity, closest first, up to top_k. Annotates each kept paper
    with `semantic_similarity` and `matched_problem`. Embedder is injectable so
    this is unit-testable without the model."""
    import numpy as np
    if not papers or not problems:
        return []
    existing_titles = existing_titles or set()

    pvec = embed_fn(problems)                                   # (P, d), normalized
    dvec = embed_fn([f"{p['title']}. {p['abstract']}" for p in papers])  # (N, d)
    sims = np.asarray(dvec) @ np.asarray(pvec).T                # (N, P) cosine
    best = sims.max(axis=1)
    best_idx = sims.argmax(axis=1)

    order = sorted(range(len(papers)), key=lambda i: float(best[i]), reverse=True)
    out: List[Dict] = []
    for i in order:
        if float(best[i]) < min_similarity:
            break
        p = papers[i]
        if p["title"].lower().strip() in existing_titles:
            continue
        out.append({**p,
                    "source": "arxiv-semantic",
                    "semantic_similarity": round(float(best[i]), 3),
                    "matched_problem": problems[int(best_idx[i])]})
        if len(out) >= top_k:
            break
    return out


def _fetch_recent_arxiv(categories: List[str], start_date: datetime, pool_size: int) -> List[Dict]:
    """Recent arXiv papers in the given categories, newest first, no keyword
    filter (that's the point — the embedding does the relevance work)."""
    import arxiv
    query = " OR ".join(f"cat:{c}" for c in categories)
    search = arxiv.Search(query=query, max_results=pool_size,
                          sort_by=arxiv.SortCriterion.SubmittedDate,
                          sort_order=arxiv.SortOrder.Descending)
    client = arxiv.Client(page_size=100, delay_seconds=5.0, num_retries=5)
    papers: List[Dict] = []
    try:
        for p in client.results(search):
            if p.published < start_date:
                continue
            papers.append({
                "id": f"arxiv-{p.entry_id.split('/')[-1]}",
                "source": "arxiv-semantic",
                "title": p.title,
                "authors": [a.name for a in p.authors],
                "date": p.published.isoformat(),
                "abstract": p.summary.replace("\n", " ").strip(),
                "url": p.entry_id,
                "pdf_url": p.pdf_url,
            })
    except Exception as e:  # arXiv rate-limited/down — skip this arm, don't abort
        print(f"[semantic] arXiv fetch failed ({e}); skipping semantic arm")
    return papers


def search_semantic(config: Dict, start_date: datetime,
                    existing_titles: Optional[set] = None) -> List[Dict]:
    """Discover recent arXiv papers semantically close to the lab's open problems."""
    sem = config.get("sources", {}).get("semantic", {})
    if not sem.get("enabled"):
        return []

    categories = sem.get("categories") or config["sources"]["arxiv"]["categories"]
    pool_size = int(sem.get("pool_size", 200))
    top_k = int(sem.get("top_k", 15))
    min_sim = float(sem.get("min_similarity", 0.35))
    model_name = sem.get("model", "sentence-transformers/all-MiniLM-L6-v2")

    print(f"[semantic] embedding recent arXiv ({', '.join(categories)}) since {start_date.date()}…")
    try:
        embed_fn = default_embedder(model_name)
    except Exception as e:  # sentence-transformers / torch not installed
        print(f"[semantic] embedder unavailable ({e}) — skipping semantic arm")
        return []

    papers = _fetch_recent_arxiv(categories, start_date, pool_size)
    if not papers:
        print("[semantic] no recent papers in pool")
        return []

    kept = rank_by_similarity(papers, problem_statements(config), embed_fn,
                              min_sim, top_k, existing_titles)
    print(f"[semantic] kept {len(kept)}/{len(papers)} (min_similarity {min_sim}, top_k {top_k})")
    return kept
