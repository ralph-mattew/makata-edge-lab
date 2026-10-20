# Automated Research-to-PoC Pipeline

**Purpose**: Weekly automated scan of latest research → validated PoC ideas → prioritized execution queue

**Goal**: Run once per week to discover new optimization opportunities for Makata AI's mobile/edge RAG system without manual research effort.

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────┐
│ WEEKLY SCAN (Automated)                                         │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 1: Research Discovery                                     │
│ ─────────────────────────────                                   │
│ • Search arXiv, HuggingFace, blogs for papers since last scan   │
│ • Filter by keywords: mobile AI, edge AI, RAG, quantization,    │
│   embeddings, retrieval, on-device LLM, etc.                    │
│ • Output: research-candidates.jsonl                             │
│ • Time: ~5-10 minutes                                           │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: Relevance Filtering (LLM-powered)                      │
│ ─────────────────────────────────                               │
│ • For each paper: extract abstract/summary                      │
│ • LLM prompt: "Is this relevant to mobile/edge RAG?"            │
│ • Filter: Keep if score ≥7/10 relevance                         │
│ • Output: relevant-research.jsonl                               │
│ • Time: ~10-15 minutes (batched LLM calls)                      │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 3: Idea Extraction (LLM-powered)                          │
│ ─────────────────────────────────                               │
│ • For each relevant paper: deep read (fetch full text if avail) │
│ • LLM prompt: "Extract 1-3 testable PoC ideas for mobile RAG"   │
│ • Generate: question, hypotheses, setup, decision rule          │
│ • Output: extracted-ideas.jsonl                                 │
│ • Time: ~20-30 minutes (full paper analysis)                    │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 4: Quality Gate Validation (Automated)                    │
│ ─────────────────────────────────                               │
│ • For each idea: run 3-gate validation                          │
│   - Gate 1: Problem validation (check against PoC 006-010)      │
│   - Gate 2: Solution understanding (verify paper details)       │
│   - Gate 3: Feasibility (iPhone constraints, ROI estimate)      │
│ • LLM evaluates each gate with scoring rubric                   │
│ • Output: validated-ideas.jsonl (approved/rejected/needs-work)  │
│ • Time: ~15-20 minutes                                          │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 5: Prioritization & Ranking                               │
│ ─────────────────────────────────                               │
│ • Calculate ROI: P(success) × Impact - P(failure) × Time_wasted │
│ • Rank by: Expected value, effort, confidence                   │
│ • Assign priority: 🔥 HIGH / 📊 MEDIUM / 🟠 LOW                 │
│ • Output: prioritized-ideas.jsonl                               │
│ • Time: ~5 minutes                                              │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ Stage 6: Idea Bank Update                                       │
│ ─────────────────────────────────                               │
│ • Merge new ideas into POC-IDEAS.md (avoid duplicates)          │
│ • Generate weekly summary report                                │
│ • Create GitHub issue with new approved ideas                   │
│ • Output: weekly-scan-YYYY-MM-DD.md                             │
│ • Time: ~5 minutes                                              │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│ HUMAN REVIEW (Manual)                                           │
│ ─────────────────────────────                                   │
│ • Review weekly summary (10-15 minutes)                         │
│ • Override any incorrect quality gate decisions                 │
│ • Select next PoC to execute                                    │
└─────────────────────────────────────────────────────────────────┘
```

**Total automated time**: ~60-90 minutes per week
**Human review time**: ~10-15 minutes per week

---

## Implementation Design

### Directory Structure

```
poc/
├── _automation/
│   ├── 1-discover-research.py       # Stage 1: Search arXiv/HF/blogs
│   ├── 2-filter-relevance.py        # Stage 2: LLM relevance scoring
│   ├── 3-extract-ideas.py           # Stage 3: Generate PoC proposals
│   ├── 4-validate-quality-gate.py   # Stage 4: Automated 3-gate checks
│   ├── 5-prioritize-ideas.py        # Stage 5: ROI ranking
│   ├── 6-update-idea-bank.py        # Stage 6: Merge to POC-IDEAS.md
│   ├── run-weekly-scan.sh           # Orchestrator (runs all stages)
│   ├── config.yaml                  # Search keywords, sources, LLM settings
│   ├── prompts/
│   │   ├── relevance-filter.txt     # Prompt for Stage 2
│   │   ├── idea-extraction.txt      # Prompt for Stage 3
│   │   ├── gate1-validation.txt     # Prompt for Gate 1
│   │   ├── gate2-validation.txt     # Prompt for Gate 2
│   │   └── gate3-validation.txt     # Prompt for Gate 3
│   └── scans/
│       ├── 2026-10-19/              # Weekly scan outputs
│       │   ├── research-candidates.jsonl
│       │   ├── relevant-research.jsonl
│       │   ├── extracted-ideas.jsonl
│       │   ├── validated-ideas.jsonl
│       │   ├── prioritized-ideas.jsonl
│       │   └── weekly-summary.md
│       └── last-scan-date.txt       # Track last successful scan
```

### Configuration File (config.yaml)

```yaml
# Research sources
sources:
  arxiv:
    enabled: true
    categories: ["cs.CL", "cs.LG", "cs.AI"]
    keywords: ["mobile AI", "edge AI", "on-device", "quantization", "RAG", "retrieval", "embedding"]

  huggingface:
    enabled: true
    blogs: true
    models: true
    keywords: ["mobile", "edge", "quantization", "ternary", "1-bit", "RAG"]

  papers_with_code:
    enabled: true
    keywords: ["mobile NLP", "edge inference", "efficient transformers"]

  blogs:
    enabled: true
    sources:
      - "https://huggingface.co/blog"
      - "https://anthropic.com/research"
      - "https://blog.google/technology/ai/"
      - "https://blogs.nvidia.com/blog/category/deep-learning/"

# LLM settings
llm:
  model: "claude-3-5-sonnet-20241022"  # Or use local model
  temperature: 0.1
  max_tokens: 4096

# Relevance filtering
relevance:
  min_score: 7.0  # Out of 10
  criteria:
    - "Applicable to mobile/edge devices (not cloud-only)"
    - "Relevant to RAG, embeddings, retrieval, or document Q&A"
    - "Practical implementation (not purely theoretical)"
    - "Novel contribution (not incremental improvement)"

# Quality gate thresholds
quality_gate:
  gate1_min_score: 7.0  # Problem validation
  gate2_min_score: 7.0  # Solution understanding
  gate3_min_score: 6.0  # Feasibility (lower threshold)

# Prioritization weights
prioritization:
  impact_weight: 0.5
  effort_weight: 0.3
  confidence_weight: 0.2

# Duplicate detection
duplicates:
  similarity_threshold: 0.8  # Cosine similarity for idea comparison
  check_against_existing: true
```

---

## Stage Details

### Stage 1: Research Discovery

**Script**: `1-discover-research.py`

**Input**: `last-scan-date.txt` (e.g., "2026-10-12")

**Process**:
1. Read last scan date
2. Search arXiv API: `search_query=cat:cs.CL+AND+(mobile+OR+edge+OR+quantization)&start_date=2026-10-12`
3. Search HuggingFace API: `/api/papers?date_gte=2026-10-12&tags=mobile,quantization`
4. Scrape recent blog posts from configured sources
5. Extract: title, authors, date, abstract/summary, URL

**Output**: `research-candidates.jsonl`
```json
{
  "id": "arxiv-2610.12345",
  "source": "arxiv",
  "title": "Ternary Quantization for Mobile LLMs",
  "authors": ["Smith, J.", "Doe, A."],
  "date": "2026-10-15",
  "abstract": "We propose...",
  "url": "https://arxiv.org/abs/2610.12345",
  "pdf_url": "https://arxiv.org/pdf/2610.12345"
}
```

**Libraries**:
- `arxiv` Python library
- `requests` for HuggingFace/blog APIs
- `feedparser` for RSS feeds

---

### Stage 2: Relevance Filtering

**Script**: `2-filter-relevance.py`

**Input**: `research-candidates.jsonl`

**Process**:
1. For each candidate, construct LLM prompt:
```
You are evaluating research relevance for a mobile/edge RAG system on iPhone.

PAPER:
Title: {title}
Abstract: {abstract}

EVALUATION CRITERIA:
- Applicable to mobile/edge devices (not cloud-only)
- Relevant to RAG, embeddings, retrieval, or document Q&A
- Practical implementation (not purely theoretical)
- Novel contribution (not incremental improvement)

Rate relevance 0-10 and explain why.

OUTPUT FORMAT:
Score: X/10
Reason: [1-2 sentences]
Key contribution: [1 sentence]
```

2. Parse LLM response, extract score
3. Filter: keep if score ≥7.0
4. Batch LLM calls (10 papers per batch)

**Output**: `relevant-research.jsonl`
```json
{
  "id": "arxiv-2610.12345",
  "source": "arxiv",
  "title": "Ternary Quantization for Mobile LLMs",
  "date": "2026-10-15",
  "url": "https://arxiv.org/abs/2610.12345",
  "pdf_url": "https://arxiv.org/pdf/2610.12345",
  "relevance_score": 9.0,
  "relevance_reason": "Directly addresses mobile LLM efficiency with practical quantization method",
  "key_contribution": "1.58-bit ternary weights retain 96% performance"
}
```

---

### Stage 3: Idea Extraction

**Script**: `3-extract-ideas.py`

**Input**: `relevant-research.jsonl`

**Process**:
1. Fetch full paper text (PDF → text extraction via `pypdf` or API)
2. For each paper, construct LLM prompt:
```
You are a research engineer designing experiments for mobile RAG optimization.

CURRENT SYSTEM:
- iPhone 15 Pro (6GB RAM budget)
- EmbeddingGemma 300M (600 MB for embeddings)
- Qwen2.5-1.5B Q4 (1.0 GB for LLM)
- Hybrid retrieval: 0.7 semantic + 0.3 BM25
- CUAD contracts dataset (397 documents, 1,325 Q&A items)
- Current recall@3: 61.4%
- Current key-fact accuracy: 67.9%

PAPER:
{full_text or extended_abstract}

TASK:
Extract 1-3 testable PoC ideas from this paper that could improve our mobile RAG system.

For each idea, provide:
1. **Question**: Testable research question (1 sentence)
2. **Why it matters**: Impact if successful (2-3 bullets)
3. **Hypotheses**: 2-3 falsifiable predictions (H1, H2, H3)
4. **Setup**: How to test it (dataset, models, metrics)
5. **Decision rule**: When to adopt vs reject (specific thresholds)
6. **Estimated effort**: Hours/days/weeks
7. **Expected outcome**: Adopt/reject/inconclusive + confidence

OUTPUT FORMAT (JSON):
{
  "ideas": [
    {
      "question": "...",
      "why_matters": ["...", "...", "..."],
      "hypotheses": ["H1: ...", "H2: ...", "H3: ..."],
      "setup": "...",
      "decision_rule": "...",
      "estimated_effort": "1-2 weeks",
      "expected_outcome": "adopt",
      "confidence": 0.7
    }
  ]
}
```

3. Parse LLM JSON response
4. Associate each idea with source paper

**Output**: `extracted-ideas.jsonl`
```json
{
  "idea_id": "arxiv-2610.12345-idea-1",
  "source_paper": "arxiv-2610.12345",
  "source_title": "Ternary Quantization for Mobile LLMs",
  "source_url": "https://arxiv.org/abs/2610.12345",
  "question": "Does ternary quantization (1.58-bit) match Q4 accuracy while reducing model size 2×?",
  "why_matters": [
    "2× smaller model footprint (0.5 GB vs 1.0 GB)",
    "Same parameter count with less memory",
    "Enables larger models in same RAM budget"
  ],
  "hypotheses": [
    "H1: Ternary Qwen2.5-1.5B key-fact rate within 2 points of Q4",
    "H2: Ternary prefill time at most 1.2× Q4",
    "H3: Model size exactly 2.0× smaller"
  ],
  "setup": "Reuse PoC 006-009 harness, test ternary Qwen2.5-1.5B vs Q4 baseline",
  "decision_rule": "If H1 and H2 hold: adopt; if H1 fails by >5 points: reject",
  "estimated_effort": "1 week",
  "expected_outcome": "adopt",
  "confidence": 0.75
}
```

---

### Stage 4: Quality Gate Validation

**Script**: `4-validate-quality-gate.py`

**Input**: `extracted-ideas.jsonl`

**Process**: For each idea, run 3-gate validation using LLM

**Gate 1: Problem Validation**
```
IDEA: {question}

GATE 1: PROBLEM VALIDATION
Does this idea address a real, measured problem in our system?

CONTEXT:
- PoC 006: Established CUAD baseline (61.4% recall, 67.9% key-fact)
- PoC 007: Hybrid retrieval baseline established
- PoC 008: Tested 3 embedding models (EmbeddingGemma best)
- PoC 009: Tested retrieval depth (3 chunks optimal)
- PoC 010: Tested BM25-only (failed: -15 points)

CRITERIA (each 0-10):
1. Root cause identified with data (not speculation)
2. Baseline failures analyzed (>20 samples)
3. Problem magnitude quantified (how many items affected?)
4. Proposed solution targets root cause

Score each criterion and provide overall Gate 1 score (0-10).
If score <7: FAIL (reject idea)
If score ≥7: PASS (proceed to Gate 2)
```

**Gate 2: Solution Understanding**
```
IDEA: {question}
PAPER: {source_url}

GATE 2: SOLUTION UNDERSTANDING
Do we understand HOW this method works, not just THAT it works?

CRITERIA (each 0-10):
1. Core mechanism explained (not black box)
2. Implementation details identified
3. Theoretical prediction documented (can we predict outcome?)
4. Failure modes understood (when does it NOT work?)

Score each criterion and provide overall Gate 2 score (0-10).
If score <7: FAIL (pause for more research)
If score ≥7: PASS (proceed to Gate 3)
```

**Gate 3: Feasibility & ROI**
```
IDEA: {question}
ESTIMATED EFFORT: {estimated_effort}
EXPECTED OUTCOME: {expected_outcome} (confidence: {confidence})

GATE 3: FEASIBILITY & ROI
Is this worth our time?

CRITERIA (each 0-10):
1. Runs on iPhone (6GB RAM, 256GB storage)
2. Memory/latency acceptable (<2× current)
3. Expected value positive: P(success) × Impact - P(failure) × Time > 0
4. Fail-fast design (can test in <20% of total effort)

Calculate ROI:
- P(success) = {confidence}
- Impact if adopt = ? (estimate 1-10)
- P(failure) = 1 - {confidence}
- Time wasted = ? (estimate hours)

Expected Value = P(success) × Impact - P(failure) × Time_wasted

Score each criterion and provide overall Gate 3 score (0-10).
If EV <0 or score <6: REJECT (low ROI)
If EV >0 and score ≥6: APPROVE
```

**Output**: `validated-ideas.jsonl`
```json
{
  "idea_id": "arxiv-2610.12345-idea-1",
  "question": "...",
  "gate1": {
    "score": 8.5,
    "verdict": "PASS",
    "criteria": {
      "root_cause": 9,
      "baseline_analysis": 8,
      "magnitude": 8,
      "targets_root_cause": 9
    },
    "reason": "Clear problem: current Q4 uses 1 GB, limiting model choice"
  },
  "gate2": {
    "score": 7.0,
    "verdict": "PASS",
    "criteria": {
      "mechanism": 7,
      "implementation": 7,
      "prediction": 7,
      "failure_modes": 7
    },
    "reason": "Paper explains ternary quantization clearly, llama.cpp support available"
  },
  "gate3": {
    "score": 8.0,
    "verdict": "APPROVE",
    "criteria": {
      "runs_iphone": 10,
      "acceptable_latency": 8,
      "positive_roi": 8,
      "fail_fast": 6
    },
    "expected_value": 4.5,
    "reason": "EV = 0.75 × 8 - 0.25 × 20 = +1.0 (positive ROI)"
  },
  "overall_verdict": "APPROVED",
  "priority": "HIGH"
}
```

---

### Stage 5: Prioritization & Ranking

**Script**: `5-prioritize-ideas.py`

**Input**: `validated-ideas.jsonl` (only APPROVED ideas)

**Process**:
1. Calculate priority score:
```python
priority_score = (
    0.5 * impact_score +        # 0-10 from Gate 3
    0.3 * (10 - effort_score) + # Invert effort (lower is better)
    0.2 * confidence            # 0-1 from idea extraction
)
```

2. Rank by priority score (descending)
3. Assign labels:
   - 🔥 HIGH: score ≥8.0, effort ≤3 days
   - 📊 MEDIUM: score 6.0-7.9
   - 🟠 LOW: score <6.0

**Output**: `prioritized-ideas.jsonl` (sorted by score)

---

### Stage 6: Idea Bank Update

**Script**: `6-update-idea-bank.py`

**Input**: `prioritized-ideas.jsonl` + `poc/POC-IDEAS.md`

**Process**:
1. Load existing idea bank
2. Detect duplicates:
   - Embed all questions (existing + new) using sentence-transformers
   - Compute cosine similarity
   - Flag if similarity >0.8
3. Merge new ideas into POC-IDEAS.md:
   - Group by theme
   - Assign PoC IDs (e.g., PoC-Q4, PoC-R6, etc.)
   - Mark status: ✅ APPROVED
4. Generate weekly summary report

**Output 1**: Updated `poc/POC-IDEAS.md`

**Output 2**: `weekly-summary.md`
```markdown
# Weekly Research Scan: 2026-10-19

**Scan period**: 2026-10-12 to 2026-10-19
**Papers scanned**: 47
**Relevant papers**: 12
**Ideas extracted**: 23
**Quality gate results**:
- ✅ Approved: 3
- ❌ Rejected: 15
- 🟡 Needs work: 5

---

## ✅ New Approved Ideas (3)

### 1. PoC-Q4: Ternary Quantization for Qwen (HIGH PRIORITY)
**Source**: [Ternary Quantization for Mobile LLMs](https://arxiv.org/abs/2610.12345)
**Question**: Does ternary quantization (1.58-bit) match Q4 accuracy while reducing model size 2×?
**Expected outcome**: Adopt (75% confidence)
**Estimated effort**: 1 week
**ROI**: +4.5 (high)

**Why execute**: 2× model size reduction enables larger models in same RAM budget

---

### 2. PoC-R6: Semantic Chunking for Contracts (MEDIUM PRIORITY)
**Source**: [Context-Aware Document Chunking](https://arxiv.org/abs/2610.23456)
**Question**: Does semantic chunking (sentence boundaries) improve recall vs fixed 500-token chunks?
**Expected outcome**: Adopt (65% confidence)
**Estimated effort**: 3 days
**ROI**: +2.1 (moderate)

---

### 3. PoC-I2: Flash Attention for Faster Prefill (LOW PRIORITY)
**Source**: [FlashAttention-3 for Mobile](https://arxiv.org/abs/2610.34567)
**Question**: Does FlashAttention reduce Qwen prefill time by ≥20%?
**Expected outcome**: Adopt (50% confidence)
**Estimated effort**: 1 week
**ROI**: +0.8 (marginal)

---

## 📊 Summary Statistics

| Metric | Value |
|--------|-------|
| New approved ideas | 3 |
| Total approved in bank | 5 (was 2) |
| Rejected this week | 15 |
| Time saved (avoided bad ideas) | ~60 hours |
| Automation time | 75 minutes |

---

## 🎯 Recommended Next Steps

1. **Execute PoC-Q4** (ternary quantization) - highest ROI
2. **Execute PoC-R6** (semantic chunking) - quick validation
3. **Monitor PoC-I2** (FlashAttention) - low confidence, defer until Q4/R6 complete

---

## 📚 Full Scan Results

See `poc/_automation/scans/2026-10-19/` for complete data:
- `research-candidates.jsonl` (47 papers)
- `relevant-research.jsonl` (12 papers)
- `extracted-ideas.jsonl` (23 ideas)
- `validated-ideas.jsonl` (3 approved)
- `prioritized-ideas.jsonl` (ranked)
```

**Output 3**: GitHub issue (optional)
```markdown
Title: [Research Scan 2026-10-19] 3 new approved PoCs

## Weekly Research Scan Results

Scanned 47 papers from Oct 12-19, found 3 high-quality PoC candidates:

1. **PoC-Q4**: Ternary quantization (2× model size reduction) - HIGH PRIORITY
2. **PoC-R6**: Semantic chunking (improve recall) - MEDIUM PRIORITY
3. **PoC-I2**: FlashAttention (faster prefill) - LOW PRIORITY

Full details: poc/_automation/scans/2026-10-19/weekly-summary.md
```

---

## Orchestration Script

**Script**: `run-weekly-scan.sh`

```bash
#!/bin/bash
set -e

SCAN_DIR="poc/_automation/scans/$(date +%Y-%m-%d)"
mkdir -p "$SCAN_DIR"

echo "=== Stage 1: Research Discovery ==="
python3 poc/_automation/1-discover-research.py --output "$SCAN_DIR/research-candidates.jsonl"

echo "=== Stage 2: Relevance Filtering ==="
python3 poc/_automation/2-filter-relevance.py \
  --input "$SCAN_DIR/research-candidates.jsonl" \
  --output "$SCAN_DIR/relevant-research.jsonl"

echo "=== Stage 3: Idea Extraction ==="
python3 poc/_automation/3-extract-ideas.py \
  --input "$SCAN_DIR/relevant-research.jsonl" \
  --output "$SCAN_DIR/extracted-ideas.jsonl"

echo "=== Stage 4: Quality Gate Validation ==="
python3 poc/_automation/4-validate-quality-gate.py \
  --input "$SCAN_DIR/extracted-ideas.jsonl" \
  --output "$SCAN_DIR/validated-ideas.jsonl"

echo "=== Stage 5: Prioritization ==="
python3 poc/_automation/5-prioritize-ideas.py \
  --input "$SCAN_DIR/validated-ideas.jsonl" \
  --output "$SCAN_DIR/prioritized-ideas.jsonl"

echo "=== Stage 6: Idea Bank Update ==="
python3 poc/_automation/6-update-idea-bank.py \
  --input "$SCAN_DIR/prioritized-ideas.jsonl" \
  --idea-bank "poc/POC-IDEAS.md" \
  --summary "$SCAN_DIR/weekly-summary.md"

echo "=== Weekly scan complete! ==="
echo "Summary: $SCAN_DIR/weekly-summary.md"
```

---

## Usage

### Initial Setup
```bash
cd /Users/rlpalomaria/Projects/makata-edge-lab
pip3 install arxiv requests feedparser pypdf sentence-transformers anthropic
```

### Run Weekly Scan
```bash
cd /Users/rlpalomaria/Projects/makata-edge-lab
./poc/_automation/run-weekly-scan.sh
```

### Review Results
```bash
# Read summary
cat poc/_automation/scans/$(date +%Y-%m-%d)/weekly-summary.md

# Check updated idea bank
git diff poc/POC-IDEAS.md
```

### Schedule Weekly (macOS launchd or cron)
```bash
# Add to crontab for every Monday at 9am
0 9 * * 1 cd /Users/rlpalomaria/Projects/makata-edge-lab && ./poc/_automation/run-weekly-scan.sh
```

---

## Expected Outcomes

### Week 1 (Initial scan)
- **Papers scanned**: 40-60 (1 week of publications)
- **Relevant papers**: 10-15 (25% pass rate)
- **Ideas extracted**: 20-30 (2 per paper)
- **Approved ideas**: 2-5 (10-20% pass quality gate)
- **Time**: 60-90 minutes automated + 10 minutes human review

### Weeks 2-4 (Steady state)
- **Papers scanned**: 30-50 (incremental)
- **Relevant papers**: 8-12
- **Ideas extracted**: 15-25
- **Approved ideas**: 1-3 per week
- **Time**: Same (60-90 min + 10 min review)

### Monthly impact
- **New approved PoCs**: 4-12 per month
- **Time saved**: ~200-300 hours (avoided bad ideas)
- **Human effort**: ~40 minutes per week (160 min/month)
- **Automation ROI**: 75× time multiplier

---

## Quality Control

### Human override required for:
1. **False positives**: LLM approved idea that's actually flawed
2. **False negatives**: LLM rejected idea that's actually promising
3. **Duplicates**: Similar idea to existing PoC
4. **Priority adjustments**: Business priorities change

### Weekly review checklist:
- [ ] Read weekly summary (5 min)
- [ ] Spot-check 2-3 rejected ideas (verify LLM judgment)
- [ ] Review approved ideas for duplicates
- [ ] Adjust priorities if needed
- [ ] Select next PoC to execute

---

## Limitations & Future Work

### Current limitations:
1. **No PDF parsing yet**: Relies on abstracts (add PyMuPDF later)
2. **No code repository scanning**: Doesn't check GitHub for new implementations
3. **No benchmark tracking**: Doesn't monitor Papers with Code leaderboards
4. **LLM cost**: ~$2-5 per scan (Claude API calls)

### Future enhancements:
1. Add GitHub trending repo analysis (popular mobile AI projects)
2. Add benchmark monitoring (detect SOTA improvements)
3. Add human feedback loop (learn from approved/rejected decisions)
4. Add cost tracking (LLM token usage)
5. Add duplicate detection across scans (temporal deduplication)

---

## Appendix: LLM Prompt Templates

See `poc/_automation/prompts/` for full prompt text files.
