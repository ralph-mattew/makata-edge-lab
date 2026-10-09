"""PoC 006 inputs: contract questions from CUAD v1, each with three fixed document sections, in the
three prompt forms Xylo builds for its chat backends.

Usage: python3 prepare.py CUAD_v1.zip OUTDIR

Writes:
- OUTDIR/items.jsonl: one line per item, with the question, the sections, whether CUAD marks the
  answer as present, the gold span and its key facts;
- OUTDIR/inputs.jsonl: one line per item, with the Gemma prompt (prefix, suffix), the Qwen prompt
  (prefix, suffix) and the FoundationModels instructions and prompt.

Everything is deterministic: the same zip gives byte-identical files.
"""

import json
import math
import random
import re
import sys
import zipfile
from pathlib import Path

from facts import key_facts

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import overlay  # noqa: E402

HERE = Path(__file__).resolve().parent
SEED = 6
PER_CLASS = 36            # items per category and class (answerable / unanswerable)
MIN_CONTRACT_WORDS = 1800  # above Xylo's whole-document limits, so every tier uses top-3 retrieval
WINDOW = 175               # Xylo's chunk size on the 6 and 8 GB tiers
MAX_SPAN_WORDS = 150       # the gold span must fit in one section with room around it
WORDS_PER_PAGE = 500       # CUAD has no page breaks; the [Page N] header uses this
SECTIONS = 3               # Xylo's chat top-K

# Xylo's chat system instruction (DocumentChatEngine, v1.2.0) and the FoundationModels lead-in. The
# text is not published: it is read from the private overlay, or a generic stand-in.
PROMPTS, PROMPT_SOURCE = overlay.load("prompts")
SYSTEM = PROMPTS["chat_system"]
FM_LEAD = PROMPTS["chat_fm_lead"]

STOPWORDS = set(
    "a an and are as at be by can do does for from has have how if in is it its of on or "
    "the this that to under what when which who with any either other party parties contract "
    "agreement".split()
)
TOKEN = re.compile(r"[a-z0-9]+")


def load_cuad(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.endswith("CUAD_v1.json"))
        return json.loads(z.read(name))["data"]


def terms(text):
    return [t for t in TOKEN.findall(text.lower()) if t not in STOPWORDS]


def bm25_rank(query, windows, k1=1.2, b=0.75):
    """Window indexes by BM25 score against the query, best first; ties by position."""
    docs = [terms(" ".join(w)) for w in windows]
    n = len(docs)
    avg = sum(map(len, docs)) / n
    q = set(terms(query))
    df = {t: sum(t in set(d) for d in docs) for t in q}
    scores = []
    for i, d in enumerate(docs):
        s = 0.0
        for t in q:
            tf = d.count(t)
            if tf:
                idf = math.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1)
                s += idf * tf * (k1 + 1) / (tf + k1 * (1 - b + b * len(d) / avg))
        scores.append(s)
    return sorted(range(n), key=lambda i: (-scores[i], i))


def span_words(spans, start, length):
    """First and last word index covering the character range [start, start + length)."""
    end = start + length
    idx = [i for i, (s, e) in enumerate(spans) if e > start and s < end]
    return (idx[0], idx[-1]) if idx else None


def sections_for(words, question, gold):
    """Three sections (start word, end word) in document order. With a gold span, one section
    contains it and the other two are the best BM25 windows that do not overlap it. Without one,
    the three best BM25 windows."""
    n = len(words)
    tiles = [(s, min(s + WINDOW, n)) for s in range(0, n, WINDOW)]
    ranked = [tiles[i] for i in bm25_rank(question, [words[s:e] for s, e in tiles])]
    if gold is None:
        chosen = ranked[:SECTIONS]
    else:
        ws, we = gold
        home = next(((s, e) for s, e in tiles if s <= ws and we < e), None)
        if home is None:  # the span crosses a tile boundary: centre a window on it
            pad = (WINDOW - (we - ws + 1)) // 2
            s = max(0, min(n - WINDOW, ws - pad))
            home = (s, s + WINDOW)
        others = [t for t in ranked if t[1] <= home[0] or t[0] >= home[1]]
        chosen = [home] + others[: SECTIONS - 1]
    return sorted(chosen)


def section_lines(words, sections):
    lines = ["\nRELEVANT SECTIONS:"]
    for s, e in sections:
        lines.append(f"[Page {1 + s // WORDS_PER_PAGE}]\n{' '.join(words[s:e])}")
    return lines


def prompts(question, lines):
    """Xylo's three chat prompts for a first turn in top-K mode, with the DOCUMENT SUMMARY part
    removed and no KEY DETAILS (see README, Method). Parts are joined as the app joins them."""
    gemma_prefix = "\n".join(["<|turn>user", SYSTEM])
    gemma_suffix = "\n".join([*lines, f"\nQuestion: {question}", "<turn|>", "<|turn>model"])
    qwen_prefix = "\n".join(["<|im_start|>system", f"{SYSTEM} /no_think<|im_end|>", "<|im_start|>user"])
    qwen_suffix = "\n".join([*lines, f"\nQuestion: {question}<|im_end|>", "<|im_start|>assistant"])
    fm_instructions = SYSTEM + "\n\n" + FM_LEAD + "\n".join(lines)
    return {
        "gemma": {"prefix": gemma_prefix, "suffix": gemma_suffix},
        "qwen": {"prefix": qwen_prefix, "suffix": qwen_suffix},
        "fm": {"instructions": fm_instructions, "prompt": question},
    }


def main():
    zip_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    questions = json.loads((HERE / "questions.json").read_text(encoding="utf-8"))
    by_category = {q["category"]: q for q in questions}

    contracts = {}
    pools = {c: {"answerable": [], "unanswerable": []} for c in by_category}
    for doc in load_cuad(zip_path):
        para = doc["paragraphs"][0]
        context = para["context"]
        spans = [m.span() for m in re.finditer(r"\S+", context)]
        if len(spans) < MIN_CONTRACT_WORDS:
            continue
        title = doc["title"]
        contracts[title] = (context, spans)
        for qa in para["qas"]:
            category = qa["id"].split("__")[-1]
            if category not in by_category:
                continue
            if qa["is_impossible"]:
                pools[category]["unanswerable"].append((title, qa["id"], None))
                continue
            first = min(qa["answers"], key=lambda a: a["answer_start"])
            gold = span_words(spans, first["answer_start"], len(first["text"]))
            if gold and gold[1] - gold[0] + 1 <= MAX_SPAN_WORDS:
                pools[category]["answerable"].append((title, qa["id"], gold))

    rng = random.Random(SEED)
    items = []
    for q in questions:
        for cls in ("answerable", "unanswerable"):
            pool = sorted(pools[q["category"]][cls])
            for title, qa_id, gold in sorted(rng.sample(pool, min(PER_CLASS, len(pool)))):
                items.append((q, cls, title, qa_id, gold))
    rng.shuffle(items)

    with open(out_dir / "items.jsonl", "w", encoding="utf-8") as fi, \
         open(out_dir / "inputs.jsonl", "w", encoding="utf-8") as fp:
        for n, (q, cls, title, qa_id, gold) in enumerate(items):
            context, spans = contracts[title]
            words = [context[s:e] for s, e in spans]
            sections = sections_for(words, q["question"], gold)
            lines = section_lines(words, sections)
            gold_text = " ".join(words[gold[0]: gold[1] + 1]) if gold else None
            item = {
                "item": n,
                "qa_id": qa_id,
                "contract": title,
                "contract_words": len(words),
                "category": q["category"],
                "question": q["question"],
                "answerable": cls == "answerable",
                "sections": [[s, e] for s, e in sections],
                "gold_words": list(gold) if gold else None,
                "gold_text": gold_text,
                "key_fact_kind": q["key_fact"],
                "key_facts": key_facts(q["key_fact"], gold_text) if gold_text and q["key_fact"] else None,
                "source": "\n".join(lines) + "\n" + q["question"],
            }
            fi.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
            fp.write(json.dumps({"item": n, **prompts(q["question"], lines)}, ensure_ascii=False, sort_keys=True) + "\n")

    counts = {}
    for q, cls, *_ in items:
        counts[(q["category"], cls)] = counts.get((q["category"], cls), 0) + 1
    print(f"prompt source: {PROMPT_SOURCE}")
    print(f"{len(contracts)} contracts with >= {MIN_CONTRACT_WORDS} words; {len(items)} items "
          f"from {len({t for *_, t, _, _ in items})} contracts")
    for q in questions:
        c = q["category"]
        print(f"  {c}: {counts.get((c, 'answerable'), 0)} answerable "
              f"(pool {len(pools[c]['answerable'])}), {counts.get((c, 'unanswerable'), 0)} "
              f"unanswerable (pool {len(pools[c]['unanswerable'])})")


if __name__ == "__main__":
    main()
