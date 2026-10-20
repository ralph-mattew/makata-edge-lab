# Automated Research-to-PoC Pipeline

**Purpose**: Weekly automated scanning of latest research → validated PoC ideas → prioritized execution queue

**Time**: 60-90 minutes automated + 10 minutes human review per week

---

## Quick Start

### 1. Install Dependencies

```bash
pip3 install --break-system-packages arxiv requests pyyaml anthropic
# Optional — only for the semantic discovery arm (sources.semantic.enabled):
pip3 install --break-system-packages sentence-transformers
```

### 2. Set API Key

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
# Optional: target a specific workspace (keys resolve to their default
# workspace otherwise). No workspace ID is baked into the source.
export ANTHROPIC_WORKSPACE_ID="wrkspc_..."
```

### 3. Run Weekly Scan

```bash
cd <path-to-repo>/poc/_automation
./run-weekly-scan.sh
```

### 4. Review Results

```bash
# View weekly summary
cat scans/$(date +%Y-%m-%d)/weekly-summary.md

# View approved ideas
cat scans/$(date +%Y-%m-%d)/prioritized-ideas.jsonl | jq .
```

---

## Pipeline Stages

The pipeline consists of 6 automated stages:

### Stage 1: Research Discovery (5-10 min)
**Script**: `1-discover-research.py`
**Input**: Last scan date
**Output**: `research-candidates.jsonl`

Searches arXiv and HuggingFace for papers since last scan matching keywords:
- mobile AI, edge AI, quantization, RAG, retrieval, embeddings, etc.

Plus an optional **semantic arm** (`sources.semantic.enabled`): embeds the lab's
open problems and recent arXiv abstracts and keeps the closest papers, so relevant
work that doesn't use the keyword vocabulary still surfaces (e.g. an on-device
training paper found via meaning, not keywords). Results are tagged with
`semantic_similarity` and the `matched_problem`.

### Stage 2: Relevance Filtering (10-15 min)
**Script**: `2-filter-relevance.py`
**Input**: `research-candidates.jsonl`
**Output**: `relevant-research.jsonl`

LLM scores each paper 0-10 for relevance to mobile/edge RAG. Keeps papers scoring ≥7/10.

### Stage 3: Idea Extraction (20-30 min)
**Script**: `3-extract-ideas.py`
**Input**: `relevant-research.jsonl`
**Output**: `extracted-ideas.jsonl`

LLM reads each paper and extracts 1-3 testable PoC ideas with:
- Question, hypotheses, setup, decision rule
- Estimated effort, expected outcome, confidence

### Stage 4: Quality Gate Validation (15-20 min)
**Script**: `4-validate-quality-gate.py`
**Input**: `extracted-ideas.jsonl`
**Output**: `validated-ideas.jsonl` (approved) + `graded-all.jsonl` (all, incl. rejects)

Runs each idea through a 3-gate quality process. The grader is an **adversarial,
source-grounded reviewer**: it judges each idea against the SOURCE PAPER's
abstract (carried on the idea as `source_abstract`), not the idea's own
self-description, and its job is to find the strongest reason to reject. Each
gate returns `evidence` (what in the source supports the claim) and `red_flags`
(claims the source does NOT support) alongside the score.

- **Gate 1**: Problem validation (is the premise grounded in source or baseline?)
- **Gate 2**: Solution understanding (does the source actually describe the mechanism / an implementation?). Optionally (`quality_gate.gate2_web_search`) the grader gets a **web_search** tool to verify a real implementation exists / has llama.cpp/MLX/Core ML support, rather than guessing from training data — it scores the implementation criterion on what it actually finds, and falls back to the ungrounded gate if the key lacks web-tool access. (Opt-in: extra cost/latency, and it makes Gate 2 stricter.)
- **Gate 3**: Feasibility & ROI (device constraints; discount unsupported resource claims)

Only ideas passing all 3 gates are approved. This decoupling of generator and
grader (plus source grounding) is what stops the generator from grading its own
homework — e.g. an idea that extrapolates a vision-classifier result to embedding
retrieval now fails Gate 2 with specific red flags instead of self-approving.

### Stage 5: Prioritization (5 min)
**Script**: `5-prioritize-ideas.py`
**Input**: `validated-ideas.jsonl`
**Output**: `prioritized-ideas.jsonl`

Ranks approved ideas by: 0.5×Impact + 0.3×Effort + 0.2×Confidence

Labels: 🔥 HIGH / 📊 MEDIUM / 🟠 LOW

### Stage 6: Idea Bank Update (5 min)
**Script**: `6-update-idea-bank.py`
**Input**: `prioritized-ideas.jsonl`
**Output**: `weekly-summary.md`

Generates weekly summary report with:
- New approved ideas (ranked by priority)
- ROI calculations
- Recommended next steps

---

## Configuration

Edit `config.yaml` to customize:

- **Search sources**: arXiv categories, HuggingFace, blogs
- **Keywords**: Search terms for each source
- **LLM settings**: Model, temperature, max_tokens, `max_retries`, `max_workers`
  (concurrent calls per stage), and optional per-stage models under `llm.models`
  (e.g. cheap `claude-haiku-4-5` for the high-volume relevance filter, a stronger
  model for extraction/gates)
- **Full-text ingestion**: `sources.fetch_fulltext` (Stage 3 fetches arXiv HTML
  for extraction instead of abstract-only; `fulltext_char_budget` caps size)
- **Quality gate thresholds**: Min scores for each gate
- **Prioritization weights**: Impact vs effort vs confidence
- **Duplicate detection**: `similarity_threshold` / `check_against_existing`
  (now enforced — Stage 6 skips ideas already in `POC-IDEAS.md`)
- **System context**: Current baseline performance

### Behavior notes

- **Scan date is committed only on full success.** Stage 1 no longer records the
  last-scan date itself; `run-weekly-scan.sh` does it after Stage 6 (via
  `1-discover-research.py --commit-date-only`), so a mid-pipeline failure
  re-scans the same window next time instead of skipping it.
- **Cross-scan paper dedup.** Stage 1 persists `scans/seen-papers.txt` and skips
  papers surfaced in earlier scans.
- **Stage 6 writes the bank.** Non-duplicate approved ideas are inserted into a
  dated "Recently Discovered" section of `POC-IDEAS.md`. Use `--dry-run` to
  preview without writing.
- **Cost/usage logging.** Each LLM stage prints a token + estimated-cost line;
  Stage 4 also writes `scans/<date>/gate-stats.json` (per-gate funnel) for
  threshold calibration.
- **Feedback loop.** `knowledge/outcomes.jsonl` is a ledger of completed-PoC
  outcomes (verdict + lesson). Gate 1 retrieves the most relevant ones
  (`_knowledge.py`; token-overlap by default, `knowledge.use_embeddings` for
  semantic) and refuses ideas that re-ask a settled question or repeat a rejected
  approach — e.g. a BM25-only idea is matched to PoC-010 [reject] and failed. Add
  a line here whenever a PoC concludes so the scanner stops re-proposing it.
- **Structured outputs + concurrency.** Stages 2/3 constrain output via
  `output_config.format` (falls back to prompt-guided JSON on older SDKs);
  stages 2/3/4 run `max_workers` calls concurrently. Prompts are split into a
  cached system block + volatile user turn. Measured: the Sonnet stages
  (extraction/gates) cache their system prefix — a re-run shows
  `cache_read` > 0. The relevance stage's block is small (and runs on Haiku,
  which has a larger cacheable minimum), so it doesn't cache — that's fine,
  since relevance runs on the cheapest model anyway.

---

## Output Structure

```
scans/
├── 2026-10-19/
│   ├── research-candidates.jsonl      (47 papers)
│   ├── relevant-research.jsonl        (12 papers, score ≥7/10)
│   ├── extracted-ideas.jsonl          (23 ideas, ~2 per paper)
│   ├── validated-ideas.jsonl          (3 ideas, passed 3 gates)
│   ├── prioritized-ideas.jsonl        (3 ideas, ranked by ROI)
│   ├── gate-stats.json                (per-gate funnel counts, for calibration)
│   ├── graded-all.jsonl               (every idea graded — approved AND rejected,
│   │                                   with per-gate evidence/red_flags; the
│   │                                   audit trail + published-rejects material)
│   └── weekly-summary.md              (Human-readable report)
├── seen-papers.txt                    (paper IDs surfaced in prior scans)
└── last-scan-date.txt                 (committed only after a full run)
```

---

## Usage Examples

### Run scan for specific date range

```bash
./1-discover-research.py --days 14 --output test/candidates.jsonl
```

### Test individual stages

```bash
# Stage 1 only
./1-discover-research.py --output test/candidates.jsonl

# Stage 2 only
./2-filter-relevance.py --input test/candidates.jsonl --output test/relevant.jsonl

# And so on...
```

### Schedule weekly (macOS launchd or cron)

```bash
# Add to crontab for every Monday at 9am
crontab -e

# Add line:
0 9 * * 1 cd <path-to-repo>/poc/_automation && ./run-weekly-scan.sh
```

---

## Expected Results

### Week 1 (Initial scan, 7 days)
- Papers scanned: 40-60
- Relevant papers: 10-15 (25%)
- Ideas extracted: 20-30
- Approved ideas: 2-5 (10-20%)

### Weeks 2+ (Incremental, 7 days)
- Papers scanned: 30-50
- Relevant papers: 8-12
- Ideas extracted: 15-25
- Approved ideas: 1-3

### Monthly impact
- New approved PoCs: 4-12 per month
- Time saved: ~200-300 hours (avoided bad ideas)
- Human effort: ~40 min/week

---

## Quality Gate Examples

### PoC 011 (Contextual Embeddings) - Should FAIL

**Gate 1**: ❌ FAIL
- No root cause analysis of WHY small chunks fail
- No baseline failure analysis
- Speculation, not data-driven

**Gate 2**: ❌ FAIL
- Didn't research HOW Anthropic implemented it
- Assumed naive text prepending would work
- Anthropic fine-tuned model; we didn't

**Gate 3**: ⚠️ MARGINAL
- Negative expected value
- Better alternatives exist (semantic chunking)

**Verdict**: Would be rejected in automation, saving ~40 hours

### PoC 010 (BM25-only) - Should PASS

**Gate 1**: ✅ PASS (9.0/10)
- Clear problem: 600 MB embedding model is large
- Baseline data: 61.4% recall established
- Magnitude: All 1,325 items affected

**Gate 2**: ✅ PASS (9.5/10)
- Simple method: disable embeddings, use pure BM25
- Clear mechanism: Okapi BM25 scoring
- Predicted outcome: Likely reject (semantic needed)

**Gate 3**: ✅ APPROVE (10.0/10)
- Minimal effort: 30 minutes
- High ROI: EV = 0.2×10 - 0.8×0.5 = +1.6
- Fail-fast: Instant validation

**Verdict**: Approved, executed, definitively answered question

---

## Troubleshooting

### No papers found
- Check arXiv keywords in config.yaml
- Verify internet connection
- Check last-scan-date.txt (may be too recent)

### LLM errors
- Verify ANTHROPIC_API_KEY is set
- Check API quota/billing
- Reduce batch size if rate-limited

### Quality gate too strict/lenient
- Adjust thresholds in config.yaml
- gate1_min_score, gate2_min_score, gate3_min_score

---

## Next Steps

After each weekly scan:

1. **Review** `weekly-summary.md` (10 min)
2. **Verify** approved ideas aren't duplicates
3. **Override** any incorrect LLM decisions
4. **Select** highest priority idea to execute
5. **Scaffold** it into a PoC folder, then refine before the first run:
   ```bash
   ./scaffold-poc.py --input scans/$(date +%Y-%m-%d)/validated-ideas.jsonl --dry-run
   ./scaffold-poc.py --input scans/$(date +%Y-%m-%d)/validated-ideas.jsonl   # writes poc/NNN-slug/README.md
   ```
   Generates the next `poc/NNN-slug/README.md` in the `_template` format,
   pre-filled with the idea's question / hypotheses / method / decision rule
   (per POC-GENERATION-WORKFLOW.md) plus the grader's pre-registration notes.

---

## Full Documentation

See [AUTOMATED-RESEARCH-PIPELINE.md](../AUTOMATED-RESEARCH-PIPELINE.md) for complete design documentation.
