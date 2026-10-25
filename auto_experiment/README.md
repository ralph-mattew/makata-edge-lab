# auto_experiment — PR-gated automated experiments

This subsystem lets the lab **run experiments automatically** without surrendering the two
things that make the lab trustworthy: **your code-quality bar** and **independent ground truth**.

It does that by splitting every experiment into a part a model may write and a part only
hand-built, deterministic code may decide:

| Who | Writes | Decides the verdict? |
|---|---|---|
| **Headless Claude Code** (`implement.py`) | the retrieval/ranking **mechanism** + a machine-readable decision rule | **No** |
| **`harness.py`** (hand-built, reviewed) | — | **Yes** — recall@3 + bootstrap + the pre-registered rule |
| **You** | nothing; you **review + merge** | you set the thresholds (in the spec) and gate every step |

The implementer is the *same Claude Code you already drive by hand* — so the code is at your
usual bar — just unattended and captured in a reviewable PR instead of a losable chat session.

## The loop (three human gates, all meaningful)

```
engine → poc/_inbox/<stub>          (ideation; daily, already automated)
  │  you PROMOTE a stub → poc/NNN-slug/      ← gate 1: what is worth running
  ▼
implement.py → headless Claude Code writes poc/NNN/experiment.py + decision.json
             → opens a PROPOSAL PR
  │  you review + MERGE the proposal PR       ← gate 2: is the mechanism + rule right
  ▼
run_experiment.py → deterministic harness runs it, applies decision.json → verdict
                  → writes results/ + poc/OUTCOMES.jsonl, opens a RESULTS PR
  │  you MERGE the results PR                 ← gate 3: accept the numbers
  ▼
engine imports the verdict on its next run (strategy credit, frontier, OP ledger)
```

"Propose via PR, and if I approve it proceeds to experiment" — the merge of the proposal PR
*is* the approval; `run_experiment.py` then runs it.

## Integrity guarantees (why a model writing the mechanism is safe here)

- **The verdict is never model-judged.** It is `recall@3` over real CUAD gold spans (top-k
  covers ≥50% of a gold span), a contract-level bootstrap CI, and a no-`eval` comparator
  applying the pre-registered `decision.json`. See `harness.verdict`.
- **The mechanism cannot see the answer.** `harness.load()` strips gold out of the corpus; the
  mechanism receives a query-only `item` (no gold) and has no gold anywhere to reach.
- **The mechanism cannot score itself.** It returns candidate scores / a top-k set; the harness
  turns that into the metric. `implement.py` aborts if the generated code touches anything
  outside its own `poc/NNN/` dir (e.g. `harness.py`).
- **The `lesson` in `OUTCOMES.jsonl` is templated from the numbers**, not written by a model.

## Mechanism contract (what `experiment.py` must expose)

```python
import sys; from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from auto_experiment import harness

def candidate_scores(ctx, item, idxs):   # -> [float] aligned to idxs   (preferred)
    ...
# or: def topk(ctx, item, idxs, k):      # -> [global row idx] chosen from idxs
# optional: def measurements():          # -> {"ram_saved_mb": 210, ...} non-recall numbers
```

`ctx` is `harness.Corpus`: `ctx.cvec` (chunk vectors), `ctx.qvec[item['qa_id']]` (query
vector), `ctx.rows[i]['chunk']` (text), and primitives `ctx.cosine/bm25/norm01/hybrid_scores`.
A mechanism needing its own embeddings builds them from `ctx.rows` text and caches under
`poc/NNN/results/raw/`. **Off limits:** `ctx.gold` and any gold span.

### `decision.json` schema (the pre-registered rule)

```json
{ "baseline": {"recall_at_3": 61.8},
  "adopt_if_all": [ {"var": "recall_at_3",       "op": ">=", "value": 61.4} ],
  "reject_if_any": [ {"var": "recall_at_3_delta", "op": "<",  "value": -2.0} ] }
```

Vars: `recall_at_3`, `hard_mean`, `weak_mean`, `n_items`, any `*_delta` vs `baseline`,
per-category `cat::<Category>`, and any key from `measurements()`. ADOPT if every
`adopt_if_all` holds; else REJECT if any `reject_if_any` holds; else INCONCLUSIVE. A rule
referencing a var the run didn't produce returns **`needs-human`** (never a silent pass).

## Manual use

```bash
python3 auto_experiment/harness.py --self-test             # sanity: reproduces ~61.8%
python3 auto_experiment/implement.py poc/039-slug --no-pr  # generate mechanism, review locally
python3 auto_experiment/implement.py poc/039-slug          # + open proposal PR
# … after you merge the proposal PR …
python3 auto_experiment/run_experiment.py poc/039-slug     # run + open results PR
```

Daily (both phases): `auto_experiment/run-experiments-daily.sh` + the launchd agent in
`automation/`. Install (the plist uses a `__LAB_DIR__` placeholder — substitute your checkout
path, since the repo forbids committing personal home paths):

```bash
sed "s|__LAB_DIR__|$PWD|g" automation/com.makata.lab-experiments.daily.plist \
  > ~/Library/LaunchAgents/com.makata.lab-experiments.daily.plist
launchctl load ~/Library/LaunchAgents/com.makata.lab-experiments.daily.plist
```

Pause with `touch STOP` in the lab root (or `launchctl unload` the plist).

## Honest limits

- **Only mechanisms that fit the recall@3 harness auto-run well** — retrieval, ranking,
  fusion, reranking, alternate/quantized embeddings. **Bespoke PoCs** (new chunking that
  changes the substrate, generation/abstention quality, on-device RAM/latency as the *primary*
  outcome) still want you in the loop; the daily job will still open a proposal PR, but review
  it knowing the harness only adjudicates retrieval recall.
- **Non-recall measurements are experiment-reported, not harness-owned.** RAM/size/latency come
  from `measurements()` (code you reviewed in the PR), not from independent ground truth. Treat
  them with the same skepticism you'd apply to any self-reported number; the *recall* claim is
  the one the harness makes unbuyable.
- **launchd, not CI** — the harness needs the local (gitignored) CUAD embeddings, so it runs on
  the Mac that has them, like the engine.
- The daily job proposes at most `--max-propose` (default 1) experiments per run to bound
  unattended Claude Code cost.
