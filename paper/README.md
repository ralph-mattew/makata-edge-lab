# Consolidated study paper

`main.tex` is a single preprint that consolidates PoCs 001–020 into one narrative:
what actually helps on-device RAG at 6 GB. It is a **draft scaffold** — the structure,
abstract and numbers are populated from the published PoC READMEs; prose sections are meant
to be tightened before submission.

## Build

```bash
cd paper
latexmk -pdf main.tex        # preferred
# or:
pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

Produces `main.pdf`. Needs a TeX distribution (TeX Live / MacTeX) with `natbib`, `booktabs`,
`hyperref`, `microtype` (all standard).

## Section map (where each claim comes from)

| Section | Source PoCs |
|---|---|
| Retrieval: what helps / doesn't | 007 (adopt), 010, 011, 009, 014, 013 |
| Hard categories = query problem | 013, 014 (eliminations); 016, 015 (fix) |
| Answer step: extraction > generation | 017, 018, 019 |
| Prompting: absence & over-refusal | 006, 008, 020 |
| Summary generation | 001, 003, 004, 005 |

Every number in the paper mirrors the matching `poc/NNN-*/README.md`. **Do not edit a figure
here ahead of its README** — the README is the source of truth.

## Before submitting

- [ ] Replace the placeholder **ORCID** (`0000-0000-0000-0000`) in `main.tex` and `.zenodo.json`.
- [ ] Resolve the `VERIFY` / `PLACEHOLDER` entries in `references.bib` (EmbeddingGemma, Gemma E2B,
      StrucChunk, RESIN, the over-refusal paper's author list).
- [ ] Re-read each cited verdict on the live site / README the day you submit (errata may exist).
- [ ] Confirm every claim is still MEASURED/OBSERVED/INFERRED-accurate.
- [ ] See [`ARXIV_CHECKLIST.md`](ARXIV_CHECKLIST.md) for the submission mechanics.

## License

This paper is CC BY 4.0, matching the lab's write-ups. Keep the same license on arXiv and Zenodo.
