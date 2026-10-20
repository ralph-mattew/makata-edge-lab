"""Feedback loop: retrieve relevant completed-PoC outcomes for a new idea.

Closes the loop so the pipeline learns from its own history — it surfaces the
most relevant prior results (adopt/reject/inconclusive + the lesson) for a given
idea, which the gate then uses to refuse re-proposing settled/rejected work and
to carry lessons forward (e.g. "PoC 011 failed because naive prepend != the
cited method").

Ranking uses token-overlap by default (fast, no deps); set
`knowledge.use_embeddings: true` to rank with the semantic embedder instead.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

HERE = Path(__file__).parent
_OUTCOMES_PATH = HERE / "knowledge" / "outcomes.jsonl"


def load_outcomes() -> List[Dict]:
    if not _OUTCOMES_PATH.exists():
        return []
    return [json.loads(l) for l in _OUTCOMES_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def _lexical_scores(query: str, outcomes: List[Dict]) -> List[float]:
    q = _tokens(query)
    out = []
    for o in outcomes:
        doc = _tokens(f"{o.get('topic','')} {o.get('question','')} {o.get('lesson','')}")
        out.append(len(q & doc) / len(q | doc) if (q or doc) else 0.0)  # Jaccard
    return out


def _embedding_scores(query: str, outcomes: List[Dict], model_name: str) -> List[float]:
    from _semantic import default_embedder
    import numpy as np
    embed = default_embedder(model_name)
    docs = [f"{o.get('topic','')}. {o.get('question','')} {o.get('lesson','')}" for o in outcomes]
    vecs = np.asarray(embed([query] + docs))
    qv, dv = vecs[0], vecs[1:]
    return [float(qv @ d) for d in dv]


def relevant_outcomes(query: str, config: Dict) -> List[Dict]:
    """Top-K prior outcomes most relevant to `query`, each with a `_score`."""
    kcfg = config.get("knowledge", {})
    if not kcfg.get("enabled", True):
        return []
    outcomes = load_outcomes()
    if not outcomes:
        return []
    top_k = int(kcfg.get("top_k", 3))
    min_score = float(kcfg.get("min_score", 0.04))

    if kcfg.get("use_embeddings"):
        try:
            scores = _embedding_scores(query, outcomes, kcfg.get("model", "sentence-transformers/all-MiniLM-L6-v2"))
        except Exception:
            scores = _lexical_scores(query, outcomes)
    else:
        scores = _lexical_scores(query, outcomes)

    ranked = sorted(zip(outcomes, scores), key=lambda t: t[1], reverse=True)
    return [{**o, "_score": round(s, 3)} for o, s in ranked[:top_k] if s >= min_score]


def format_prior_results(query: str, config: Dict) -> str:
    """A prompt-ready block of the most relevant prior lab results, or a short
    'none' line. Goes in the volatile (user) half of a gate prompt."""
    hits = relevant_outcomes(query, config)
    if not hits:
        return "(no closely-related prior lab result found)"
    lines = []
    for o in hits:
        lines.append(f"- {o['id']} [{o['verdict']}] {o.get('topic','')}: {o.get('lesson','')}")
    return "\n".join(lines)
