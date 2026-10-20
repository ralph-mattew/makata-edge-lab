# PoC inbox — staged idea proposals (not yet registered PoCs)

This folder is the **staging area** for PoC ideas auto-exported from the lab's ideation engine
(the private `idea-evolution-engine`). Each subfolder is a `Status: planned` proposal rendered
into the `../_template` format, carrying its engine provenance (source paper, 3-gate scores,
null-control margin, tournament rank).

**These are proposals, not experiments.** They are gate-approved and null-control-screened, but
**not empirically validated** — nothing here has been run.

## How to promote a proposal to a real PoC

1. Review the stub. If it's worth running, pick the next number in the `poc/NNN-<slug>/` sequence.
2. Move it: `git mv poc/_inbox/<date>-<slug> poc/NNN-<slug>`.
3. Fill the **Method** (exact model files + SHA-256, devices, settings, measurements, repetitions)
   and finalize the **Decision rule** — see `../POC-GENERATION-WORKFLOW.md`.
4. Register it: commit the README *before the first run* (the registration timestamp).
5. Discard proposals you won't run — this inbox is meant to be pruned, not to accumulate.

Proposals are regenerated each engine run; an existing folder is never overwritten.
