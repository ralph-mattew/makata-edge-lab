"""Load text that cannot be published, from a private overlay, with a generic stand-in.

Some PoCs run on prompts and keyword tables taken from a private app. Those texts are not in
this repository. The registered runs used them; `private/<name>.json` holds them on the machine
that ran the PoC (the directory is gitignored). If it is missing, the files under `generic/` are
used instead. A stand-in has the same structure and a similar shape, not the same wording, so
results built from it are a replication attempt, not the registered run. Each `prepare.py` prints
which source it used; the inputs' recorded SHA-256 shows whether the registered text was used.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRIVATE = Path(os.environ.get("LAB_PRIVATE_DIR", ROOT / "private"))
GENERIC = ROOT / "generic"


def load(name):
    """Return (data, source) for `name`; source is "private" or "generic"."""
    private = PRIVATE / f"{name}.json"
    if private.is_file():
        return json.loads(private.read_text(encoding="utf-8")), "private"
    print(f"overlay: {private} not found; using the generic stand-in generic/{name}.json. "
          "Results will not match the registered runs.", file=sys.stderr)
    return json.loads((GENERIC / f"{name}.json").read_text(encoding="utf-8")), "generic"
