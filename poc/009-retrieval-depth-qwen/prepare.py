"""PoC 009 inputs: PoC 007's items, with the sections Xylo's retriever would pick at several depths,
in Qwen's chat prompt from PoC 006.

Usage: python3 prepare.py CUAD_v1.zip OUTDIR

Reads PoC 007's committed files (items.jsonl, chunks-index.jsonl, scores-kw/nl/eg.jsonl), runs its
retriever (`retrieve` in 007's summarize.py) for each condition below, cuts the chosen chunks out
of the contract, and builds Qwen's first-turn chat prompt with PoC 006's `prompts()`.

Writes:
- OUTDIR/items.jsonl: one line per item: the question, the gold span and its key facts;
- OUTDIR/selection-<condition>.jsonl: per item, the chosen chunks (best first), how many words they
  hold, how many were dropped by the word cap, the share of the gold span they cover, and the
  numbers of two or more digits in the prompt's document and question text (for the
  unsupported-number measure);
- OUTDIR/inputs-<condition>.jsonl: per item, the prompts in the form PoC 006's GGUFQA harness reads.
  Only `qwen` is used; `gemma` is empty. These files hold the private chat prompt, are not
  committed, and are rebuilt byte for byte by this script.

Everything is deterministic: the same zip and the same PoC 007 files give byte-identical output.
"""

import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
P6 = LAB / "006-doc-qa-fm-gemma-qwen"
P7 = LAB / "007-embedding-retrieval-recall"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(P6))
p6 = load("prepare006", P6 / "prepare.py")
s6 = load("summarize006", P6 / "summarize.py")
s7 = load("summarize007", P7 / "summarize.py")

# name -> (semantic backend, number of chunks). Hybrid scoring, 0.7 semantic + 0.3 keyword, as Xylo.
CONDITIONS = {
    "eg-k1": ("eg", 1),
    "eg-k3": ("eg", 3),
    "eg-k5": ("eg", 5),
    "nl-k3": ("nl", 3),
    "nl-k5": ("nl", 5),
}
WORD_CAP = 1000  # most words (overlap included) the chunks of one prompt may hold; see README


def read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def main():
    zip_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    raw7 = P7 / "results" / "raw"
    items7 = read(raw7 / "items.jsonl")
    index = {c["contract"]: c["chunks"] for c in read(raw7 / "chunks-index.jsonl")}
    scores = {m: {r["item"]: r["scores"] for r in read(raw7 / f"scores-{m}.jsonl")}
              for m in ("kw", "nl", "eg")}
    key_fact_kind = {q["category"]: q["key_fact"]
                     for q in json.loads((P6 / "questions.json").read_text(encoding="utf-8"))}

    wanted = {it["contract"] for it in items7}
    contracts = {}
    for doc in p6.load_cuad(zip_path):
        if doc["title"] in wanted:
            context = doc["paragraphs"][0]["context"]
            contracts[doc["title"]] = [m.group() for m in re.finditer(r"\S+", context)]
    assert set(contracts) == wanted, "contracts missing from the zip"

    files = {"items": open(out_dir / "items.jsonl", "w", encoding="utf-8")}
    for name in CONDITIONS:
        files[f"sel-{name}"] = open(out_dir / f"selection-{name}.jsonl", "w", encoding="utf-8")
        files[f"in-{name}"] = open(out_dir / f"inputs-{name}.jsonl", "w", encoding="utf-8")
    dump = lambda o: json.dumps(o, ensure_ascii=False, sort_keys=True) + "\n"
    stats = {name: {"words": [], "dropped": 0, "capped": 0, "covered": 0} for name in CONDITIONS}

    for it in items7:
        n, title = it["item"], it["contract"]
        words, ranges = contracts[title], index[title]
        assert ranges[-1][1] <= len(words)
        pages = [r[2] for r in ranges]
        gold = it["gold_words"]
        gold_text = " ".join(words[gold[0]: gold[1] + 1])
        kind = key_fact_kind[it["category"]]
        files["items"].write(dump({
            "item": n, "qa_id": it["qa_id"], "contract": title, "contract_words": len(words),
            "category": it["category"], "question": it["question"], "answerable": True,
            "gold_words": gold, "gold_text": gold_text, "key_fact_kind": kind,
            "key_facts": p6.key_facts(kind, gold_text) if kind else None,
        }))
        for name, (backend, k) in CONDITIONS.items():
            ranked = s7.retrieve(scores[backend][n], scores["kw"][n], pages, k, 0.7, 0.3)
            assert len(ranked) == k
            chosen = list(ranked)
            while len(chosen) > 1 and sum(ranges[i][1] - ranges[i][0] for i in chosen) > WORD_CAP:
                chosen.pop()
            lines = ["\nRELEVANT SECTIONS:"]
            for i in sorted(chosen):
                s, e = ranges[i][0], ranges[i][1]
                lines.append(f"[Page {ranges[i][2]}]\n{' '.join(words[s:e])}")
            source = "\n".join(lines) + "\n" + it["question"]
            section_words = sum(ranges[i][1] - ranges[i][0] for i in chosen)
            files[f"sel-{name}"].write(dump({
                "item": n, "chunks": chosen, "section_words": section_words,
                "dropped": k - len(chosen), "coverage": s7.coverage(chosen, ranges, gold),
                "numbers": sorted(s6.numbers(source)),
            }))
            prompt = p6.prompts(it["question"], lines)["qwen"]
            files[f"in-{name}"].write(dump({"item": n, "gemma": {"prefix": "", "suffix": ""},
                                            "qwen": prompt}))
            st = stats[name]
            st["words"].append(section_words)
            st["dropped"] += k - len(chosen)
            st["capped"] += len(chosen) < k
            st["covered"] += s7.coverage(chosen, ranges, gold) >= 0.5

    for f in files.values():
        f.close()
    print(f"prompt source: {p6.PROMPT_SOURCE}")
    print(f"{len(items7)} items from {len(wanted)} contracts")
    for name, st in stats.items():
        w = sorted(st["words"])
        print(f"  {name}: section words median {w[len(w) // 2]}, p95 {w[int(0.95 * len(w))]}, "
              f"max {w[-1]}; {st['capped']} items lose chunks to the {WORD_CAP}-word cap "
              f"({st['dropped']} chunks); recall {100 * st['covered'] / len(items7):.1f}%")


if __name__ == "__main__":
    main()
