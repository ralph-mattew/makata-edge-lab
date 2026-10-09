"""PoC 007 inputs: contracts split into pages, and contract questions with CUAD's answer span.

Usage: python3 prepare.py CUAD_v1.zip OUTDIR

Writes:
- OUTDIR/contracts.jsonl: one line per contract that has at least one item: its title, a language
  sample (the first 500 characters, as Xylo's language detector reads them) and its pages. Pages
  keep the paragraph breaks ("\\n\\n") and hold about 500 words each, because CUAD has no page
  breaks and Xylo chunks page by page.
- OUTDIR/items.jsonl: one line per item: the question and the gold answer span, as word indexes
  into the contract (words are runs of non-space characters, as in PoC 006).

Only answerable items are written; this PoC measures whether the answer's text is retrieved.
Everything is deterministic: the same zip gives byte-identical files.
"""

import json
import random
import re
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SEED = 7
PER_CATEGORY = 100        # answerable items per category, or all of them if fewer
MIN_CONTRACT_WORDS = 1800  # above Xylo's whole-document limits, so retrieval is top-K
MAX_SPAN_WORDS = 150       # as PoC 006
WORDS_PER_PAGE = 500


def load_cuad(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith("CUAD_v1.json"))
        return json.loads(z.read(name))["data"]


def span_words(spans, start, length):
    """First and last word index covering the character range [start, start + length)."""
    end = start + length
    idx = [i for i, (s, e) in enumerate(spans) if e > start and s < end]
    return (idx[0], idx[-1]) if idx else None


def pages_of(context):
    """Paragraphs (split on blank lines) grouped into pages of about WORDS_PER_PAGE words."""
    pages, current, count = [], [], 0
    for paragraph in (p.strip() for p in context.split("\n\n")):
        if not paragraph:
            continue
        current.append(paragraph)
        count += len(paragraph.split())
        if count >= WORDS_PER_PAGE:
            pages.append("\n\n".join(current))
            current, count = [], 0
    if current:
        pages.append("\n\n".join(current))
    return pages


def main():
    zip_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    by_category = {q["category"]: q for q in questions}

    contracts = {}
    pools = {c: [] for c in by_category}
    for doc in load_cuad(zip_path):
        para = doc["paragraphs"][0]
        context = para["context"]
        spans = [m.span() for m in re.finditer(r"\S+", context)]
        if len(spans) < MIN_CONTRACT_WORDS:
            continue
        title = doc["title"]
        contracts[title] = context
        for qa in para["qas"]:
            category = qa["id"].split("__")[-1]
            if category not in by_category or qa["is_impossible"]:
                continue
            first = min(qa["answers"], key=lambda a: a["answer_start"])
            gold = span_words(spans, first["answer_start"], len(first["text"]))
            if gold and gold[1] - gold[0] + 1 <= MAX_SPAN_WORDS:
                pools[category].append((title, qa["id"], gold))

    rng = random.Random(SEED)
    items = []
    for q in questions:
        pool = sorted(pools[q["category"]])
        for title, qa_id, gold in sorted(rng.sample(pool, min(PER_CATEGORY, len(pool)))):
            items.append((q, title, qa_id, gold))
    rng.shuffle(items)

    used = sorted({title for _, title, _, _ in items})
    with open(out_dir / "contracts.jsonl", "w", encoding="utf-8") as f:
        for title in used:
            context = contracts[title]
            pages = pages_of(context)
            assert sum(len(p.split()) for p in pages) == len(context.split()), title
            f.write(json.dumps({"contract": title, "language_sample": context[:500], "pages": pages},
                               ensure_ascii=False, sort_keys=True) + "\n")
    with open(out_dir / "items.jsonl", "w", encoding="utf-8") as f:
        for n, (q, title, qa_id, gold) in enumerate(items):
            f.write(json.dumps({
                "item": n, "qa_id": qa_id, "contract": title, "category": q["category"],
                "question": q["question"], "gold_words": list(gold),
            }, ensure_ascii=False, sort_keys=True) + "\n")

    counts = {}
    for q, *_ in items:
        counts[q["category"]] = counts.get(q["category"], 0) + 1
    print(f"{len(contracts)} contracts with >= {MIN_CONTRACT_WORDS} words; {len(items)} items "
          f"from {len(used)} contracts")
    for q in questions:
        c = q["category"]
        print(f"  {c}: {counts.get(c, 0)} (pool {len(pools[c])})")


if __name__ == "__main__":
    main()
