#!/usr/bin/env python3
"""Build PoC 003's inputs: 20 CUAD contracts, cut to Xylo's input size, in Xylo's Summary prompt.

Usage: python3 prepare.py CUAD_v1.zip OUT.jsonl

Selection: the 510 files under CUAD_v1/full_contract_txt/, sorted by path, every 25th starting
at the first, first 20. Each text is whitespace-normalized and cut to its first 2,500
characters, the way Xylo cuts the document to its budget (a plain prefix, mid-word allowed).

The prompt is Xylo's Summary template (ChatML path, English; private app, commit 196a729). Its
text is not published: it is read from the private overlay (see scripts/overlay.py), with a
generic stand-in when the overlay is absent. The app's primer for this template is empty, so
the prompt ends right after the assistant header.
"""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import overlay  # noqa: E402

PREFIX = "CUAD_v1/full_contract_txt/"
STEP = 25
COUNT = 20
MAX_CHARS = 2500

PROMPTS, PROMPT_SOURCE = overlay.load("prompts")
SYSTEM = PROMPTS["summary_system"]
USER = PROMPTS["summary_user"]


def build_prompt(document):
    user = USER.replace("{document}", document)
    return (
        f"<|im_start|>system\n{SYSTEM}<|im_end|>\n"
        f"<|im_start|>user\n{user}<|im_end|>\n"
        "<|im_start|>assistant\n"
    )


def normalize(raw):
    t = raw.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t\f\v\u00a0]+", " ", t)
    t = "\n".join(line.strip() for line in t.split("\n"))
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    zip_path, out_path = sys.argv[1], sys.argv[2]
    with zipfile.ZipFile(zip_path) as z:
        names = sorted(n for n in z.namelist() if n.startswith(PREFIX) and n.endswith(".txt"))
        if len(names) != 510:
            sys.exit(f"expected 510 contract texts, found {len(names)}")
        chosen = names[::STEP][:COUNT]
        with open(out_path, "w", encoding="utf-8") as out:
            for doc, name in enumerate(chosen):
                text = normalize(z.read(name).decode("utf-8", errors="replace"))
                document = text[:MAX_CHARS]
                prompt = build_prompt(document)
                out.write(json.dumps({
                    "doc": doc,
                    "file": name[len(PREFIX):],
                    "source_chars": len(text),
                    "input_chars": len(document),
                    "input_sha256": sha256(document),
                    "prompt_sha256": sha256(prompt),
                    "input": document,
                    "prompt": prompt,
                }, ensure_ascii=False) + "\n")
    print(f"wrote {len(chosen)} inputs to {out_path} (prompt source: {PROMPT_SOURCE})")


if __name__ == "__main__":
    main()
