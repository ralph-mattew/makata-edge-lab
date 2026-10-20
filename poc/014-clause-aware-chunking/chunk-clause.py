#!/usr/bin/env python3
"""PoC 014 — build page-based and clause-aware chunk sets from CUAD (deterministic).

Both conditions operate on the SAME contract word stream that the recall scorer uses,
`words = " ".join(pages).split()`, so every emitted chunk is a contiguous slice of
that stream and the PoC 007/011 `chunk_span` scorer can locate it unchanged:

  page   (baseline)  — PoC 007's `own` page chunks, emitted verbatim (reproduces 61.4%).
  clause (treatment) — segment the stream on clause/section boundaries, with size guards.

Clause boundaries are detected line-by-line on the original text (newlines within a
page survive the join), then mapped to word indices by cumulative word count — so the
clause chunk `chunk` text equals `" ".join(words[i:j])` and its span [i, j-1] is known
exactly (used for the H3 span-integrity metric). No model, no network.

Output (results/raw/): chunks-page.jsonl, chunks-clause.jsonl
Each row: {"contract", "chunk", "span": [start_word, end_word]}  (span inclusive)
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
RAW = HERE / "results" / "raw"

WORD_CAP = 200     # split a clause longer than this (keeps embedding context bounded; cf. page mean 48 / Q3 74)
MERGE_FLOOR = 15   # merge a clause shorter than this into the next (avoids heading-only fragments)

# Line-start patterns that mark the beginning of a clause/section.
NUMBERED = re.compile(r"^\(?\d{1,3}(?:\.\d{1,3}){0,3}[.)]\s+\S")       # "5. ", "12.3 ", "(1) " ...
LETTERED = re.compile(r"^\((?:[a-z]|[ivxlcdm]{1,4})\)\s+\S")           # "(a) ", "(iv) "
KEYWORD  = re.compile(r"^(?:ARTICLE|SECTION|CLAUSE|EXHIBIT|SCHEDULE|APPENDIX|ANNEX)\b", re.I)
ALLCAPS  = re.compile(r"^[A-Z][A-Z0-9 ,.&/'\"()-]{3,}$")               # "GOVERNING LAW" (whole short line in caps)

# Inline token markers (CUAD text often lacks newlines, so clause markers must be
# detected within a running token stream, not only at line starts).
TOK_LETTERED = re.compile(r"^\((?:[a-z]|[ivxlcdm]{1,4})\)$")           # "(a)" "(iv)" as a standalone token
TOK_SUBNUM   = re.compile(r"^\d{1,2}\.\d{1,2}(?:\.\d{1,2})?$")         # "2.1" "5.3.1" subsection number
TOK_SECKW    = re.compile(r"^(?:Section|Article|Clause|ARTICLE|SECTION)$")
CAPWORD      = re.compile(r"^[A-Z][A-Z'&./-]{1,}$")                    # an all-caps alpha token (len>=2)
STOP_CAPS    = {"I", "A", "THE", "AND", "OR", "OF", "TO", "IN", "BY", "AS", "IF", "NO", "ANY"}


def is_boundary(line: str) -> bool:
    s = line.strip()
    if not s:
        return False
    if NUMBERED.match(s) or LETTERED.match(s) or KEYWORD.match(s):
        return True
    toks = s.split()
    if 2 <= len(toks) <= 12 and ALLCAPS.match(s) and sum(c.isalpha() for c in s) >= 3:
        return True
    return False


def token_boundaries(words: list[str]) -> set[int]:
    """Clause starts detected inline in the token stream (newline-independent)."""
    b = set()
    nxt_cap = lambda i: i + 1 < len(words) and words[i + 1][:1].isupper()
    for i, w in enumerate(words):
        if TOK_LETTERED.match(w) and nxt_cap(i):                       # "(a) Term ..."
            b.add(i)
        elif TOK_SUBNUM.match(w) and nxt_cap(i):                       # "2.1 Payment ..."
            b.add(i)
        elif TOK_SECKW.match(w) and i + 1 < len(words) and re.match(r"^\d", words[i + 1]):
            b.add(i)                                                   # "Section 5 ..."
        elif CAPWORD.match(w) and w not in STOP_CAPS and i + 1 < len(words) \
                and CAPWORD.match(words[i + 1]) and words[i + 1] not in STOP_CAPS \
                and (i == 0 or not CAPWORD.match(words[i - 1])):       # start of an ALL-CAPS heading run
            b.add(i)
    return b


def clause_boundaries(full: str) -> list[int]:
    """Word indices (into full.split()) where a clause starts. Union of line-start
    heuristics (good for structured docs) and inline token markers (for unstructured
    runs). Always includes 0."""
    words = full.split()
    bounds, wpos = {0}, 0
    for line in full.split("\n"):
        n = len(line.split())
        if n and is_boundary(line):
            bounds.add(wpos)
        wpos += n
    bounds |= token_boundaries(words)
    return sorted(bounds)


def apply_size_guards(segments: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """segments: list of (start, end_exclusive) word spans. Merge tiny, split overlong."""
    # 1) merge segments shorter than MERGE_FLOOR into the following segment
    merged: list[list[int]] = []
    for s, e in segments:
        if merged and (e - s) < MERGE_FLOOR and (merged[-1][1] - merged[-1][0]) < WORD_CAP:
            merged[-1][1] = e
        elif merged and (merged[-1][1] - merged[-1][0]) < MERGE_FLOOR:
            merged[-1][1] = e  # previous was tiny → absorb this one
        else:
            merged.append([s, e])
    # 2) split segments longer than WORD_CAP into <=WORD_CAP pieces
    out: list[tuple[int, int]] = []
    for s, e in merged:
        if e - s <= WORD_CAP:
            out.append((s, e))
        else:
            for p in range(s, e, WORD_CAP):
                out.append((p, min(p + WORD_CAP, e)))
    return out


def iter_page_chunks():
    for line in open(P007 / "chunks.jsonl"):
        rec = json.loads(line)
        for ch in rec["chunks"]:
            yield rec["contract"], ch["own"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", type=int, default=0, help="cap to first N contracts (0 = all)")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    allowed = set(list(contracts)[:args.contracts]) if args.contracts else None

    # ---- page baseline: PoC 007 `own` chunks, with their located span ----
    page_counts = []
    with open(RAW / "chunks-page.jsonl", "w") as f:
        by_c = {}
        for c, own in iter_page_chunks():
            if allowed is not None and c not in allowed:
                continue
            by_c.setdefault(c, []).append(own)
        for c, owns in by_c.items():
            words = " ".join(contracts[c].get("pages", []) or []).split()
            # locate each own as a contiguous slice (first match), for span-integrity
            cursor = 0
            for own in owns:
                span = locate(words, own.split(), cursor)
                f.write(json.dumps({"contract": c, "chunk": own,
                                    "span": [span[0], span[1]] if span else None}) + "\n")
                if span:
                    cursor = span[0]  # monotonic hint; page chunks are in order
            page_counts.append(len(owns))

    # ---- clause treatment: segment the word stream on clause boundaries ----
    clause_counts = []
    with open(RAW / "chunks-clause.jsonl", "w") as f:
        for c, rec in contracts.items():
            if allowed is not None and c not in allowed:
                continue
            full = " ".join(rec.get("pages", []) or [])
            words = full.split()
            bounds = clause_boundaries(full) + [len(words)]
            segs = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1) if bounds[i + 1] > bounds[i]]
            segs = apply_size_guards(segs)
            for s, e in segs:
                f.write(json.dumps({"contract": c, "chunk": " ".join(words[s:e]),
                                    "span": [s, e - 1]}) + "\n")
            clause_counts.append(len(segs))

    import statistics as st
    print(f"page   chunks: {sum(page_counts)} over {len(page_counts)} contracts "
          f"(median {st.median(page_counts):.0f}/contract)")
    print(f"clause chunks: {sum(clause_counts)} over {len(clause_counts)} contracts "
          f"(median {st.median(clause_counts):.0f}/contract)")
    ratio = sum(clause_counts) / max(sum(page_counts), 1)
    print(f"clause/page chunk-count ratio: {ratio:.2f}x  (H4 guard: <=1.3x)")


def locate(words, ow, start=0):
    if not ow:
        return None
    first = ow[0]
    for i in range(start, len(words) - len(ow) + 1):
        if words[i] == first and words[i:i + len(ow)] == ow:
            return (i, i + len(ow) - 1)
    # fall back to a global search if the monotonic hint overshot
    for i in range(0, len(words) - len(ow) + 1):
        if words[i] == first and words[i:i + len(ow)] == ow:
            return (i, i + len(ow) - 1)
    return None


if __name__ == "__main__":
    main()
