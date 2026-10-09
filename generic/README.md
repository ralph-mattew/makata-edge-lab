# Generic stand-ins

Some PoCs ran on prompts and keyword tables from a private app. Those texts are not published
here. They live in a gitignored `private/` directory (`prompts.json`, `keywords.json`) on the
machine that ran the registered runs.

The files in this directory have the same structure and a similar shape, with different wording.
Without `private/`, `prepare.py` and the retrieval harness read them and print a warning. Results
built from a stand-in are a replication attempt on a similar prompt, not the registered run.

`scripts/overlay.py` does the loading. Set `LAB_PRIVATE_DIR` to point at another overlay.
Each PoC's README records the SHA-256 of the inputs the registered run used, so a reader with an
overlay can check that it matches.
