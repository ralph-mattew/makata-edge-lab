"""HuggingFace model-release discovery for Stage 1.

For an edge lab, a new *model release* (a quantized embedder, a small reranker, a
ternary LLM with GGUF/MLX) is often more immediately PoC-worthy than a paper — and
it won't show up in an arXiv/paper scan. This arm queries the HF models API for
recent releases matching the lab's interests and turns each into a candidate the
normal relevance/extraction/gates can judge (a model release is a strong Gate-2
case: the implementation provably exists).

Opt-in and keyword-targeted (the raw recent-model feed is noisy); the downstream
adversarial relevance gate cuts the rest. Network errors degrade to [].
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

import requests

_API = "https://huggingface.co/api/models"
_DEFAULT_KEYWORDS = [
    "embedding gguf", "reranker gguf", "embedding mlx",
    "quantized embedding", "ternary", "bitnet", "1-bit llm", "mobile embedding",
]


def _parse_dt(s: str):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except Exception:
        return None


def to_candidate(model: Dict) -> Dict:
    """Shape an HF model record into the candidate dict the pipeline expects
    (title/authors/date/abstract/url), factual metadata only."""
    mid = model.get("id") or model.get("modelId") or ""
    tags = model.get("tags") or []
    abstract = (
        f"HuggingFace model release. "
        f"Pipeline: {model.get('pipeline_tag') or 'n/a'}. "
        f"Library: {model.get('library_name') or 'n/a'}. "
        f"Tags: {', '.join(tags[:12]) or 'n/a'}. "
        f"{model.get('downloads', 0)} downloads, {model.get('likes', 0)} likes."
    )
    return {
        "id": f"hf-model-{mid}",
        "source": "huggingface-model",
        "title": mid,
        "authors": [model.get("author", "")] if model.get("author") else [],
        "date": model.get("createdAt", ""),
        "abstract": abstract,
        "url": f"https://huggingface.co/{mid}",
        "pdf_url": "",
    }


def search_hf_models(config: Dict, start_date: datetime) -> List[Dict]:
    cfg = config.get("sources", {}).get("huggingface_models", {})
    if not cfg.get("enabled"):
        return []
    keywords = cfg.get("keywords") or _DEFAULT_KEYWORDS
    per_kw = int(cfg.get("limit_per_keyword", 10))
    min_likes = int(cfg.get("min_likes", 0))
    max_total = int(cfg.get("max_total", 15))

    print(f"[hf-models] scanning HF model releases since {start_date.date()}…")
    seen, out = set(), []
    for kw in keywords:
        try:
            resp = requests.get(_API, params={
                "search": kw, "sort": "createdAt", "direction": -1,
                "limit": per_kw, "full": "true",
            }, timeout=20)
            resp.raise_for_status()
            models = resp.json()
        except Exception as e:
            print(f"[hf-models] query '{kw}' failed ({e}); skipping")
            continue
        for m in models:
            mid = m.get("id") or m.get("modelId")
            if not mid or mid in seen:
                continue
            created = _parse_dt(m.get("createdAt"))
            if created is None or created < start_date:
                continue
            if (m.get("likes") or 0) < min_likes:
                continue
            seen.add(mid)
            out.append(to_candidate(m))

    out.sort(key=lambda c: c["date"], reverse=True)
    out = out[:max_total]
    print(f"[hf-models] kept {len(out)} recent model releases")
    return out
