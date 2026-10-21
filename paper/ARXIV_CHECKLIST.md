# Publishing checklist: Zenodo + arXiv

Two independent tracks. Do **Zenodo first** (no gatekeeping, instant DOI), then arXiv for reach.
They cite each other.

---

## 0. One-time prerequisites

- [ ] **ORCID** — register free at <https://orcid.org> and put the iD in `main.tex` and `.zenodo.json`.
- [ ] Decide the author list and order; update `CITATION.cff`, `.zenodo.json`, and `main.tex` to match.
- [ ] Confirm license is **CC BY 4.0** everywhere (paper, Zenodo, arXiv) — matches the lab's write-ups.

---

## 1. Zenodo (archive + DOI, no endorsement)

Zenodo mints a DOI immediately and has first-class GitHub integration. Two options:

### Option A — archive the whole repo via GitHub (recommended)
1. [ ] Sign in to <https://zenodo.org> with GitHub; under **Settings → GitHub**, flip the switch
       **on** for `ralph-mattew/makata-edge-lab`.
2. [ ] Ensure `.zenodo.json` (repo root, already added) has the final ORCID/authors.
3. [ ] Cut a GitHub **release** with a tag (e.g. `v0.1.0`). Zenodo auto-archives the tarball and
       issues a **version DOI** plus a stable **concept DOI** (always resolves to the latest).
4. [ ] Copy the concept DOI into `CITATION.cff` (`doi:` field) and the paper's reproducibility
       section; commit that.

### Option B — upload the PDF as a standalone record
1. [ ] Build `main.pdf`, create a new Zenodo upload, set type **Publication → Preprint**,
       license **CC BY 4.0**, add keywords from `.zenodo.json`.
2. [ ] Add related identifier → the GitHub repo URL (relation: *is supplement to*).
3. [ ] Publish → get the DOI.

> Tip: you can do both — a software/record DOI for the repo snapshot and the paper PDF as a
> related record. Keep the concept DOI stable across versions.

---

## 2. arXiv (preprint, moderated, needs endorsement for first-timers)

### 2a. Category & endorsement
- [ ] Primary category: **cs.IR** (Information Retrieval). Cross-list **cs.CL** and/or **cs.LG**.
- [ ] First submission to a category may require an **endorsement**. Paths:
  - auto-endorsed if you submit from a recognised academic/institutional email; otherwise
  - ask someone who has published in cs.IR/cs.CL to endorse (a 2-minute action); or
  - skip arXiv and use **TechRxiv** (IEEE, no endorsement) as a fallback preprint server.
- [ ] Create the arXiv account and link your ORCID.

### 2b. Package the source (arXiv prefers LaTeX source, not PDF-only)
- [ ] Build locally first: `latexmk -pdf main.tex` must succeed with **no errors**.
- [ ] Run bibtex so `main.bbl` exists, then include it — arXiv does **not** run bibtex; upload
      `main.tex`, `main.bbl`, and any figures (none here yet). `references.bib` is optional.
- [ ] Zip exactly those files (flat, no nested folder): `main.tex`, `main.bbl`.
- [ ] Check it compiles clean against the arXiv TeX Live version (use their test-compile step).

### 2c. Metadata & license
- [ ] Title / authors / abstract (paste the abstract from `main.tex`; plain text, no LaTeX macros).
- [ ] License: **CC BY 4.0**.
- [ ] Add the **Zenodo DOI** in the comments field (e.g. "Code and raw results: <DOI>").
- [ ] Submit → goes to moderation hold → typically announced next business day. You get an arXiv
      ID and an arXiv-assigned DOI (DataCite).

### 2d. After it's live
- [ ] Add the arXiv ID/DOI to `CITATION.cff`, the website (`/lab`), and `.zenodo.json`
      (`related_identifiers`, relation *is identical to* / *is preprint of*).
- [ ] If you later submit to a venue, check its anonymity-period policy — most ML venues allow a
      preprint but restrict advertising during review.

---

## 3. Optional: peer-reviewed venue
Good fits for a reproducibility / efficiency empirical study:
- EMNLP/ACL **efficient-NLP** tracks or **Findings**
- NeurIPS **ENLSP** (Efficient Natural Language and Speech Processing) workshop
- **MLSys**, or on-device / edge-ML workshops

A workshop gives peer-reviewed credibility on top of the arXiv preprint; preprinting first is
generally allowed.

---

## Quick reference

| | Zenodo | arXiv | TechRxiv |
|---|---|---|---|
| DOI | instant | yes (on announce) | yes |
| Endorsement | none | first-timers may need it | none |
| Format | any (PDF, repo) | LaTeX source preferred | PDF |
| Scholar-indexed | yes | yes (best reach) | yes |
| Do it | **now** | after endorsement | arXiv fallback |
