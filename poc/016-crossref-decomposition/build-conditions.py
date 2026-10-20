#!/usr/bin/env python3
"""PoC 016 — build the xref chunk condition + decomposition templates (deterministic).

Reuses PoC 014's page chunks (results/raw/chunks-page.jsonl, each with its word `span`)
as the baseline. Produces:

  chunks-xref.jsonl   — each page chunk with the text of any clause it cross-references
                        ("Section 3.2", "Exhibit A", ...) appended BEFORE embedding. The
                        `span` is unchanged (still the original chunk's location, used for
                        recall scoring); only the embedded/BM25 text grows. `changed` marks
                        rows that actually gained reference text (so embed step can reuse the
                        PoC-014 page vector for unchanged rows).
  decomp-templates.json — fixed, hand-authored sub-query templates per hard category
                        (NON-generative, PoC-011-safe). Easy categories map to [] (use raw q).

No model, no network.
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path

HERE = Path(__file__).resolve().parent
P007 = HERE.parent / "007-embedding-retrieval-recall" / "results" / "raw"
P014 = HERE.parent / "014-clause-aware-chunking" / "results" / "raw"
RAW = HERE / "results" / "raw"

REF_WORDS = 150   # words of referenced clause to append
APPEND_CAP = 150  # cap appended text per chunk

# Hard-category decomposition templates (authored once; reused across all contracts).
DECOMP_TEMPLATES = {
    "Exclusivity": [
        "exclusive dealing restriction on the parties",
        "exceptions or carve-outs to the exclusivity obligation",
        "which party is bound by exclusivity and in what territory or field",
    ],
    "Non-Compete": [
        "non-compete restriction prohibiting competing business",
        "duration and geographic scope of the non-compete",
        "exceptions to the non-competition covenant",
    ],
    "Change Of Control": [
        "change of control or change in ownership provision",
        "assignment or termination rights triggered by change of control",
        "consent required on a merger acquisition or sale of the company",
    ],
}


def contract_text(c):
    return " ".join(c.get("pages", []) or [])


KW = {"EXHIBIT", "SCHEDULE", "APPENDIX", "ARTICLE", "ANNEX"}


def build_heading_index(words):
    """Two reliable indexes of where a clause/section begins in the contract:
      num:    distinctive numbered clause starts ("3.2") -> offset
      phrase: an UPPERCASE keyword heading ("EXHIBIT A", "ARTICLE V") -> offset
    Single bare letters ('A') are deliberately NOT indexed on their own — too common
    to resolve reliably; an exhibit is resolved via the 'EXHIBIT A' phrase instead."""
    num, phrase = {}, {}
    for i, w in enumerate(words):
        tok = w.strip(".)(")
        # numbered clause start: distinctive, followed by a capitalized word
        if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){1,3}", tok) and tok not in num \
                and i + 1 < len(words) and words[i + 1][:1].isupper():
            num[tok] = i
        # uppercase keyword heading phrase: "EXHIBIT A", "ARTICLE V" (keyword in CAPS =
        # heading, not an inline "see exhibit a" reference)
        if w.upper() == w and w in KW and i + 1 < len(words):
            lab = words[i + 1].strip(".)(").upper()
            key = f"{w} {lab}"
            if key not in phrase:
                phrase[key] = i
    return {"num": num, "phrase": phrase}


def resolve_refs(chunk_text, words, heading_idx):
    """Append the referenced clause's text for references found in chunk_text, using only
    reliably-resolvable targets (distinctive section numbers, uppercase heading phrases)."""
    num, phrase = heading_idx["num"], heading_idx["phrase"]
    targets = []  # offsets to append
    # Section/subsection numbers (must contain a dot to be distinctive, e.g. 3.2)
    for m in re.finditer(r"\b(?:Section|Sections|§)\s+(\d{1,3}(?:\.\d{1,3})+)\b", chunk_text, re.I):
        if m.group(1) in num:
            targets.append(num[m.group(1)])
    # Keyword heading phrases: Exhibit/Schedule/Appendix/Article/Annex <label>
    for m in re.finditer(r"\b(Exhibit|Schedule|Appendix|Article|Annex)\s+([A-Z]|[IVXLC]{1,6}|\d{1,3})\b", chunk_text):
        key = f"{m.group(1).upper()} {m.group(2).upper()}"
        if key in phrase:
            targets.append(phrase[key])
    appended, used = [], set()
    for off in targets:
        if off in used:
            continue
        used.add(off)
        appended.extend(words[off:off + REF_WORDS])
        if len(appended) >= APPEND_CAP:
            break
    return " ".join(appended[:APPEND_CAP])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--contracts", type=int, default=0, help="cap to first N contracts (0=all)")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    contracts = {c["contract"]: c for c in map(json.loads, open(P007 / "contracts.jsonl"))}
    words_cache, head_cache = {}, {}
    for name, c in contracts.items():
        w = contract_text(c).split()
        words_cache[name] = w
        head_cache[name] = build_heading_index(w)

    page_rows = [json.loads(l) for l in open(P014 / "chunks-page.jsonl")]
    allowed = set(list(contracts)[:args.contracts]) if args.contracts else None

    changed = 0
    with open(RAW / "chunks-xref.jsonl", "w") as f:
        for r in page_rows:
            c = r["contract"]
            if allowed is not None and c not in allowed:
                continue
            extra = resolve_refs(r["chunk"], words_cache.get(c, []), head_cache.get(c, {}))
            # don't append text that's already in the chunk (avoid trivial self-dupe)
            if extra and extra[:40] not in r["chunk"]:
                out = {"contract": c, "chunk": r["chunk"] + " [REF] " + extra,
                       "span": r["span"], "changed": True}
                changed += 1
            else:
                out = {"contract": c, "chunk": r["chunk"], "span": r["span"], "changed": False}
            f.write(json.dumps(out) + "\n")

    (RAW / "decomp-templates.json").write_text(json.dumps(DECOMP_TEMPLATES, indent=2))
    total = sum(1 for r in page_rows if allowed is None or r["contract"] in allowed)
    print(f"chunks-xref.jsonl: {total} chunks, {changed} gained reference text "
          f"({100*changed/max(total,1):.1f}%)")
    print(f"decomp-templates.json: {sum(len(v) for v in DECOMP_TEMPLATES.values())} "
          f"sub-queries across {len(DECOMP_TEMPLATES)} hard categories")


if __name__ == "__main__":
    main()
