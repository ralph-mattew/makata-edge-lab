"""PoC 007 index: word ranges of the chunks, and the BM25 reference scores.

Usage: python3 index.py RAW_DIR

Reads RAW_DIR/contracts.jsonl, chunks.jsonl and items.jsonl. Writes:
- RAW_DIR/chunks-index.jsonl: per contract, each chunk as [first word, last word + 1, page], in
  the contract's word indexes (words are runs of non-space characters). The range includes the
  30-word overlap the chunk starts with, because the model reads it.
- RAW_DIR/scores-bm25.jsonl: per item, the BM25 score of every chunk against the question. A
  reference arm outside Xylo's pipeline, as in PoC 006 (k1 1.2, b 0.75).

chunks.jsonl holds the contract text and is not committed; the index and the scores are enough to
re-score everything.
"""

import json
import math
import re
import sys
from bisect import bisect_left, bisect_right
from collections import Counter
from pathlib import Path

STOPWORDS = set(
    "a an and are as at be by can do does for from has have how if in is it its of on or "
    "the this that to under what when which who with any either other party parties contract "
    "agreement".split()
)
TOKEN = re.compile(r"[a-z0-9]+")


def terms(text):
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


def read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def chunk_ranges(chunks, words):
    """[first word, last word + 1, page] per chunk, overlap included.

    The sentence splitter sometimes cuts inside a whitespace-delimited word, and the chunk text
    rejoins the pieces with a space, so counting words drifts. Characters other than whitespace
    are never added or dropped, so chunks are placed by those characters and mapped back to words.
    """
    ends, total = [], 0
    for w in words:
        total += len(w)
        ends.append(total)
    out, position = [], 0
    for chunk in chunks:
        own = sum(len(w) for w in chunk["own"].split())
        overlap = sum(len(w) for w in chunk["overlap"].split())
        first = bisect_right(ends, position - overlap)
        last = bisect_left(ends, position + own) + 1
        out.append([first, last, chunk["page"]])
        position += own
    return out, position, total


def bm25_scores(query, docs, k1=1.2, b=0.75):
    n = len(docs)
    lengths = [len(d) for d in docs]
    avg = sum(lengths) / n
    q = set(terms(query))
    counters = [Counter(d) for d in docs]
    df = {t: sum(1 for c in counters if t in c) for t in q}
    scores = []
    for c, length in zip(counters, lengths):
        s = 0.0
        for t in q:
            tf = c.get(t, 0)
            if tf:
                idf = math.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1)
                s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avg))
        scores.append(round(s, 6))
    return scores


def main():
    raw = Path(sys.argv[1])
    words = {c["contract"]: [w for p in c["pages"] for w in p.split()] for c in read(raw / "contracts.jsonl")}
    chunks = {c["contract"]: c["chunks"] for c in read(raw / "chunks.jsonl")}
    items = read(raw / "items.jsonl")

    with open(raw / "chunks-index.jsonl", "w", encoding="utf-8") as f:
        for title, cs in chunks.items():
            ranges, placed, total = chunk_ranges(cs, words[title])
            assert placed == total, f"{title}: chunks hold {placed} characters, contract has {total}"
            f.write(json.dumps({"contract": title, "words": len(words[title]), "chunks": ranges},
                               sort_keys=True) + "\n")

    docs = {}
    with open(raw / "scores-bm25.jsonl", "w", encoding="utf-8") as f:
        for item in items:
            title = item["contract"]
            if title not in docs:
                docs[title] = [
                    terms((c["overlap"] + " " + c["own"]) if c["overlap"] else c["own"]) for c in chunks[title]
                ]
            f.write(json.dumps({"item": item["item"], "contract": title, "mode": "bm25",
                                "scores": bm25_scores(item["question"], docs[title])}, sort_keys=True) + "\n")
    print(f"{len(chunks)} contracts, {sum(len(c) for c in chunks.values())} chunks, {len(items)} items")


if __name__ == "__main__":
    main()
