# Ideation engine — moved to a private repo

The automated research→idea pipeline that used to live here has been extracted into a dedicated
**private** repository, **`idea-evolution-engine`**, where it is being generalized into a
domain-configurable, self-evolving idea engine (engine + domain packs; human-gated
self-improvement).

**Why:** the engine (and its self-modification machinery) is the core innovation and is
safety-sensitive; it belongs in a private repo. This public lab remains the **open-science
layer** — PoC pre-registrations, results, and *published rejects* (see `poc/0xx-*` and
`POC-IDEAS.md`), which the engine consumes as ground truth.

History for the engine was preserved via `git subtree split` during the move. This directory is
intentionally left as a pointer; the engine is no longer developed here.
