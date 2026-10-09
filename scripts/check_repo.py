#!/usr/bin/env python3
"""Repository checks run in CI: personal data, large or third-party files, JSON, PoC results."""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 5 * 1024 * 1024
FORBIDDEN_SUFFIXES = (".gguf", ".safetensors", ".mlmodel", ".onnx", ".pt", ".bin")
FORBIDDEN_DIRS = (".mlpackage/", ".mlmodelc/")
SKIP_TEXT = {"LICENSE", "LICENSE-CC-BY-4.0"}
PRIVATE = [
    (re.compile(r"/Users/(?!Shared/)[^/\s\"']+"), "macOS home directory path"),
    (re.compile(r"/home/[^/\s\"']+"), "Linux home directory path"),
    (re.compile(r"[A-Za-z]:\\\\?Users\\\\?[^\\\s\"']+"), "Windows home directory path"),
    (re.compile(r"\b[0-9A-F]{8}-[0-9A-F]{16}\b"), "iOS device UDID"),
]


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    return [ROOT / p for p in out.decode().split("\0") if p]


def main():
    errors = []
    files = tracked_files()
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_BYTES:
            errors.append(f"{rel}: larger than 5 MB; attach large artifacts to a release instead")
        if rel.endswith(FORBIDDEN_SUFFIXES) or any(d in rel for d in FORBIDDEN_DIRS):
            errors.append(f"{rel}: model weights must not be committed")
        if path.name in SKIP_TEXT or rel == "scripts/check_repo.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern, what in PRIVATE:
            m = pattern.search(text)
            if m:
                line = text.count("\n", 0, m.start()) + 1
                errors.append(f"{rel}:{line}: looks like a {what}; remove personal data")
        if rel.endswith(".json"):
            try:
                json.loads(text)
            except json.JSONDecodeError as e:
                errors.append(f"{rel}: invalid JSON ({e})")

    tracked = {p.relative_to(ROOT).as_posix() for p in files}
    for readme in sorted((ROOT / "poc").glob("[0-9][0-9][0-9]-*/README.md")):
        poc = readme.parent.relative_to(ROOT).as_posix()
        status = re.search(r"^\| Status \| (.+?) \|", readme.read_text(encoding="utf-8"), re.M)
        if status and "planned" not in status.group(1).lower():
            if not any(t.startswith(f"{poc}/results/raw/") for t in tracked):
                errors.append(f"{poc}: status is '{status.group(1)}' but results/raw/ is empty")
    for rep in sorted((ROOT / "poc").glob("[0-9][0-9][0-9]-*/replications/*/")):
        r = rep.relative_to(ROOT).as_posix()
        if f"{r}/README.md" not in tracked:
            errors.append(f"{r}: missing README.md (copy poc/_template/REPLICATION.md)")
        if not any(t.startswith(f"{r}/results/raw/") for t in tracked):
            errors.append(f"{r}: missing results/raw/")

    for e in errors:
        print(f"::error::{e}")
    print(f"checked {len(files)} files, {len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
