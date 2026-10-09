#!/usr/bin/env python3
"""Build PoC 004's inputs: PoC 003's 20 CUAD inputs, in two prompt variants.

Usage: python3 prepare.py CUAD_v1.zip OUT_DIR

Writes OUT_DIR/inputs-xylo.jsonl and OUT_DIR/inputs-no-end-line.jsonl.

- xylo: PoC 003's prompt, unchanged. It is built by PoC 003's own prepare.py, so the two PoCs
  cannot drift apart; its file is byte-identical to PoC 003's results/raw/inputs.jsonl.
- no-end-line: the same prompt with the single line that closes the worked example removed.
  Nothing else changes. The line's text is in the private overlay (`summary_end_line`).
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import overlay  # noqa: E402

HERE = Path(__file__).resolve().parent
POC003_PREPARE = HERE.parent / "003-qwen-sampler-stop-behavior" / "prepare.py"
END_LINE = overlay.load("prompts")[0]["summary_end_line"]


def sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    zip_path, out_dir = sys.argv[1], Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    xylo = out_dir / "inputs-xylo.jsonl"
    subprocess.run([sys.executable, str(POC003_PREPARE), zip_path, str(xylo)], check=True)

    rows = [json.loads(line) for line in xylo.read_text(encoding="utf-8").splitlines() if line.strip()]
    with open(out_dir / "inputs-no-end-line.jsonl", "w", encoding="utf-8") as out:
        for row in rows:
            if row["prompt"].count(END_LINE) != 1:
                sys.exit(f"doc {row['doc']}: expected exactly one '{END_LINE.strip()}' line")
            row["prompt"] = row["prompt"].replace(END_LINE, "")
            row["prompt_sha256"] = sha256(row["prompt"])
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {len(rows)} inputs per variant to {out_dir}")


if __name__ == "__main__":
    main()
