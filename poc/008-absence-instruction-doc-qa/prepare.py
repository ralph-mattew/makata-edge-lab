"""PoC 008 inputs: PoC 006's 986 items and sections, in three prompt variants.

Usage: python3 prepare.py CUAD_v1.zip OUTDIR

Runs PoC 006's prepare.py (same items, same sections, same base prompts, same private overlay or
generic stand-in), then derives the two variants by adding the text in variants.json:

- base:   PoC 006's prompts, unchanged.
- rule:   `rule` is appended to the system instruction, in all three prompt forms.
- rule-q: `rule` as in `rule`, and `reminder` is also added after the question.

Writes OUTDIR/items.jsonl (identical to PoC 006's) and OUTDIR/inputs-<variant>.jsonl. Everything is
deterministic. Each replacement is checked to apply exactly once, and the base file is the one
PoC 006's prepare.py wrote, so the base arm cannot drift from PoC 006.
"""

import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
P6 = HERE.parent / "006-doc-qa-fm-gemma-qwen"
sys.path.insert(0, str(P6))
spec = importlib.util.spec_from_file_location("prepare006", P6 / "prepare.py")
p6 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p6)

VARIANTS = json.loads((HERE / "variants.json").read_text(encoding="utf-8"))
RULE, REMINDER = VARIANTS["rule"], VARIANTS["reminder"]
NAMES = ["base", "rule", "rule-q"]


def replaced_once(text, old, new):
    assert text.count(old) == 1, f"expected exactly one {old[:40]!r}"
    return text.replace(old, new)


def derive(line, question, reminder):
    """One inputs line with the rule added to the system instruction, and the reminder after the
    question when `reminder` is true."""
    system = p6.SYSTEM
    g, q, f = line["gemma"], line["qwen"], line["fm"]
    g["prefix"] = replaced_once(g["prefix"], system, f"{system} {RULE}")
    q["prefix"] = replaced_once(q["prefix"], f"{system} /no_think", f"{system} {RULE} /no_think")
    assert f["instructions"].startswith(system)
    f["instructions"] = f"{system} {RULE}" + f["instructions"][len(system):]
    if reminder:
        g["suffix"] = replaced_once(g["suffix"], f"\nQuestion: {question}\n<turn|>",
                                    f"\nQuestion: {question}\n{REMINDER}\n<turn|>")
        q["suffix"] = replaced_once(q["suffix"], f"\nQuestion: {question}<|im_end|>",
                                    f"\nQuestion: {question}\n{REMINDER}<|im_end|>")
        assert f["prompt"] == question
        f["prompt"] = f"{question}\n\n{REMINDER}"
    return line


def main():
    zip_path, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    sys.argv = [sys.argv[0], str(zip_path), str(out_dir)]
    p6.main()

    base = out_dir / "inputs.jsonl"
    (out_dir / "inputs-base.jsonl").write_bytes(base.read_bytes())
    base.unlink()
    items = {}
    with open(out_dir / "items.jsonl", encoding="utf-8") as f:
        for raw in f:
            it = json.loads(raw)
            items[it["item"]] = it["question"]

    for name in NAMES[1:]:
        with open(out_dir / "inputs-base.jsonl", encoding="utf-8") as src, \
             open(out_dir / f"inputs-{name}.jsonl", "w", encoding="utf-8") as dst:
            for raw in src:
                line = derive(json.loads(raw), items[json.loads(raw)["item"]], reminder=name == "rule-q")
                dst.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")
    print("variants: " + ", ".join(NAMES))


if __name__ == "__main__":
    main()
