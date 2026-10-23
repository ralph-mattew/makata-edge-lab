# PoC inbox — staged idea proposals (not yet registered PoCs)

This folder is the **staging area** for PoC ideas auto-exported from the lab's ideation engine
(the private `idea-evolution-engine`). Each subfolder is a `Status: planned` proposal rendered
into the `../_template` format, carrying its engine provenance (source paper, 3-gate scores,
null-control margin, tournament rank).

**These are proposals, not experiments.** They are gate-approved and null-control-screened, but
**not empirically validated** — nothing here has been run.

## How to promote a proposal to a real PoC

1. Review the stub. If it's worth running, pick the next number in the `poc/NNN-<slug>/` sequence.
2. Move it: `git mv poc/_inbox/<date>-<slug> poc/NNN-<slug>` (if the drop is untracked, `git mv` errors —
   `mkdir poc/NNN-<slug> && git mv`/`mv` the two `.md` files, then remove the empty source dir).
3. Fill the **Method** (exact model files + SHA-256, devices, settings, measurements, repetitions)
   and finalize the **Decision rule** — see `../POC-GENERATION-WORKFLOW.md`.
4. Register it: commit the README *before the first run* (the registration timestamp).
5. Discard proposals you won't run — this inbox is meant to be pruned, not to accumulate.

Proposals are regenerated each engine run; an existing folder is never overwritten.

## ⚠️ Promotion hygiene (do not re-learn this the hard way)

**Never `git add poc/_inbox` (or `git add -A`/`git add .`) in a PoC commit.** The engine drops
proposals here as **untracked** files; a bulk add silently sweeps the *sibling* proposals you did not
touch into your PoC's commit. This has bitten us twice (stray dirs carried onto `main` via an
unrelated PoC PR, then needing a cleanup PR).

Stage **only** the specific paths you changed:

```bash
# promoting PoC-NNN and discarding one sibling:
git add poc/NNN-<slug>                 # the promoted PoC only
git rm -r  poc/_inbox/<discarded-slug> # each discard, explicitly (tracked)
rm -rf     poc/_inbox/<discarded-slug> # each discard, explicitly (untracked)
git status --short                     # VERIFY: no unexpected poc/_inbox/* staged
```

If you must touch the inbox, add exact subpaths (`git add poc/_inbox/<this-slug>`), never the folder.
