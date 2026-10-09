"""PoC 008 scoring: PoC 006's measures on three prompt variants, with the corrected detector and the
decision rule.

Usage: python3 summarize.py [RESULTS_DIR]   (default: results)

Reads RESULTS_DIR/raw/items.jsonl and RESULTS_DIR/raw/gen-<backend>-<variant>.jsonl. Writes
RESULTS_DIR/summary.json and RESULTS_DIR/summary.md. On the first call it also writes the blinded
audit sheet, RESULTS_DIR/audit/sheet.csv, and its key, RESULTS_DIR/audit/key.json. Once
RESULTS_DIR/audit/labels.csv exists, the detector's agreement with it is part of the summary.

PoC 006's scoring (output clean-up, key facts, unsupported numbers) is imported unchanged. The only
scoring change is the answer-or-absent detector; see "Detector v2" below.
"""

import csv
import importlib.util
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
P6 = HERE.parent / "006-doc-qa-fm-gemma-qwen"
sys.path.insert(0, str(P6))
_spec = importlib.util.spec_from_file_location("summarize006", P6 / "summarize.py")
s6 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s6)

BACKENDS = ["fm", "gemma-e2b", "qwen-1.5b"]
FM, GEMMA, QWEN = BACKENDS
VARIANTS = ["base", "rule", "rule-q"]
TREATED = ["rule", "rule-q"]
BOOTSTRAP_RESAMPLES = 10_000
AUDIT_PER_BACKEND = 40
AUDIT_MIN_AGREEMENT = 0.90
# Decision thresholds (README, Decision rule)
NO_GAIN = 0.02
MIN_GAIN = 0.05
MAX_ANSWER_DROP = 0.05
MAX_KEY_FACT_DROP = 0.05
PHRASE = "the provided sections do not contain this"

# --- Detector v2 -----------------------------------------------------------------------------------
# PoC 006's detector with two changes, made after PoC 006's audit and before any PoC 008 output
# existed: (1) leading characters that are not letters or digits are dropped before the first
# sentence is matched, so ": No" and "*-No*" read as "no"; (2) "No later than", "No more than" and
# similar openings (a comparison word, an optional "-ly" adverb, then "than") are answers. Every other
# pattern is PoC 006's.

NO_THAN = re.compile(
    r"^(no|none|nope)\b(?!\s+(?:later|earlier|sooner|more|less|fewer|greater|longer|shorter|higher|lower)"
    r"(?:\s+\w+ly)?\s+than\b)")
ABSENT_V2 = [NO_THAN] + s6.ABSENT[1:]


def first_sentence_v2(text):
    return re.sub(r"^[^a-z0-9]+", "", s6.first_sentence(text))


def call_v2(text):
    """"absent", "answer" or "empty"."""
    if not text.strip():
        return "empty"
    s = first_sentence_v2(text)
    return "absent" if any(p.search(s) for p in ABSENT_V2) else "answer"


def score(item, gen):
    """PoC 006's row, with the call and `correct` from detector v2; v1's call is kept."""
    r = s6.score(item, gen)
    r["call_v1"] = r["call"]
    r["fixed_phrase"] = r["text"].strip().strip(".").strip().lower() == PHRASE
    if r["call"] not in ("error", "empty"):
        r["call"] = call_v2(r["text"])
        r["correct"] = (r["call"] == "answer") if item["answerable"] else (r["call"] == "absent")
    return r


def as_v1(rows):
    out = []
    for r in rows:
        r = dict(r)
        r["call"] = r["call_v1"]
        if r["call"] not in ("error", "empty"):
            r["correct"] = (r["call"] == "answer") if r["answerable"] else (r["call"] == "absent")
        out.append(r)
    return out


# --- Bootstrap -------------------------------------------------------------------------------------

def per_contract(rows):
    """Per contract: [answerable, answered, unanswerable, said absent, key-fact items, key fact
    right, items, any unsupported]."""
    agg = defaultdict(lambda: [0] * 8)
    for r in rows:
        a = agg[r["contract"]]
        if r["answerable"]:
            a[0] += 1
            a[1] += r["correct"]
        else:
            a[2] += 1
            a[3] += r["correct"]
        if "key_fact" in r:
            a[4] += 1
            a[5] += r["key_fact"]
        a[6] += 1
        a[7] += r["any_unsupported"]
    return agg


def div(x, y):
    return x / y if y else float("nan")


def measures(t):
    a, u = div(t[1], t[0]), div(t[3], t[2])
    return {"balanced": (a + u) / 2, "answer_rate": a, "absent_rate": u,
            "key_fact": div(t[5], t[4]), "any_unsupported": div(t[7], t[6])}


def statistics_spec():
    """Every compared quantity: name -> function of {(backend, variant): measures}."""
    spec = {}
    for b in BACKENDS:
        for v in TREATED:
            for m in ("balanced", "answer_rate", "absent_rate", "key_fact", "any_unsupported"):
                spec[f"{b}:{v}:{m}"] = lambda x, b=b, v=v, m=m: x[(b, v)][m] - x[(b, "base")][m]
    for b in (FM, QWEN):
        spec[f"{b}:rule-q_minus_rule:absent_rate"] = \
            lambda x, b=b: x[(b, "rule-q")]["absent_rate"] - x[(b, "rule")]["absent_rate"]
    spec["qwen_gain_minus_fm_gain:rule:absent_rate"] = \
        lambda x: (x[(QWEN, "rule")]["absent_rate"] - x[(QWEN, "base")]["absent_rate"]) \
        - (x[(FM, "rule")]["absent_rate"] - x[(FM, "base")]["absent_rate"])
    return spec


def bootstrap_all(rows):
    """Contract-level bootstrap of every statistic at once: contracts are resampled with replacement,
    with all their items, the same resample for every arm. 10,000 resamples, seed 0."""
    keys = [(b, v) for b in BACKENDS for v in VARIANTS]
    agg = {k: per_contract(rows[k]) for k in keys}
    contracts = sorted(agg[keys[0]])
    spec = statistics_spec()

    def values(sample):
        out = {}
        for k in keys:
            t = [0] * 8
            for c in sample:
                for i, v in enumerate(agg[k][c]):
                    t[i] += v
            out[k] = measures(t)
        return out

    point_values = values(contracts)
    rng = random.Random(0)
    draws = {name: [] for name in spec}
    for _ in range(BOOTSTRAP_RESAMPLES):
        x = values([rng.choice(contracts) for _ in contracts])
        for name, fn in spec.items():
            d = fn(x)
            if d == d:
                draws[name].append(d)
    result = {}
    for name, fn in spec.items():
        ds = sorted(draws[name])
        k = len(ds)
        result[name] = {"diff": fn(point_values), "ci95": [ds[int(0.025 * k)], ds[int(0.975 * k) - 1]]}
    return result


# --- Audit -----------------------------------------------------------------------------------------

def audit(results, rows, items):
    """Blinded audit of the detector: AUDIT_PER_BACKEND outputs per backend, drawn over all three
    variants, shuffled, with no arm, variant or detector call on the sheet."""
    folder = results / "audit"
    sheet, key_path, labels = folder / "sheet.csv", folder / "key.json", folder / "labels.csv"
    if not sheet.exists():
        folder.mkdir(exist_ok=True)
        rng = random.Random(0)
        picks = []
        for b in BACKENDS:
            pool = [(v, r) for v in VARIANTS for r in rows[(b, v)]]
            for v, r in rng.sample(pool, AUDIT_PER_BACKEND):
                if r["call"] not in ("error", "empty"):
                    picks.append((b, v, r))
        rng.shuffle(picks)
        with open(sheet, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "question", "answer", "label (answer / absent)"])
            for n, (b, v, r) in enumerate(picks):
                w.writerow([n, items[r["item"]]["question"], r["text"], ""])
        key_path.write_text(json.dumps(
            [{"id": n, "backend": b, "variant": v, "item": r["item"], "call": r["call"], "call_v1": r["call_v1"],
              "fixed": r["fixed_phrase"]}
             for n, (b, v, r) in enumerate(picks)], indent=1) + "\n")
    if not labels.exists():
        return None
    key = {k["id"]: k for k in json.loads(key_path.read_text())}
    with open(labels, newline="", encoding="utf-8") as f:
        got = [r for r in csv.reader(f)][1:]
    labelled = [(key[int(r[0])], r[3].strip().lower()) for r in got if r[3].strip()]
    agree = sum(k["call"] == lab for k, lab in labelled)
    agree_v1 = sum(k["call_v1"] == lab for k, lab in labelled)
    rest = [(k, lab) for k, lab in labelled if not k["fixed"]]
    by_backend = {b: [(k, lab) for k, lab in labelled if k["backend"] == b] for b in BACKENDS}
    return {
        "labelled": len(labelled),
        "agreement": agree / len(labelled) if labelled else float("nan"),
        "agreement_v1": agree_v1 / len(labelled) if labelled else float("nan"),
        "fixed_phrase_outputs": len(labelled) - len(rest),
        "agreement_not_fixed_phrase": sum(k["call"] == lab for k, lab in rest) / len(rest) if rest else float("nan"),
        "by_backend": {b: sum(k["call"] == lab for k, lab in v) / len(v) for b, v in by_backend.items() if v},
        "disagreements": [{"id": k["id"], "backend": k["backend"], "variant": k["variant"], "item": k["item"],
                           "detector": k["call"], "label": lab} for k, lab in labelled if k["call"] != lab],
    }


# --- Decision --------------------------------------------------------------------------------------

def decide_variant(b, v, rate, bs, aud):
    """One backend, one treated variant against base. First match wins."""
    g = bs[f"{b}:{v}:balanced"]
    crit = {
        "c1_balanced_gain_at_least_5_ci_above_0": g["diff"] >= MIN_GAIN and g["ci95"][0] > 0,
        "c2_answer_rate_not_worse_than_minus_5": rate[(b, v)]["answer_rate"] >= rate[(b, "base")]["answer_rate"] - MAX_ANSWER_DROP,
        "c3_key_fact_not_worse_than_minus_5": rate[(b, v)]["key_fact"] >= rate[(b, "base")]["key_fact"] - MAX_KEY_FACT_DROP,
    }
    if aud is None:
        verdict = "pending: audit labels missing"
    elif aud["agreement"] < AUDIT_MIN_AGREEMENT:
        verdict = "inconclusive: detector not valid"
    elif g["diff"] < NO_GAIN:
        verdict = "reject: no gain"
    elif all(crit.values()):
        verdict = "adopt (host stage)"
    elif crit["c1_balanced_gain_at_least_5_ci_above_0"]:
        verdict = "reject: trade-off"
    else:
        verdict = "inconclusive"
    return {"criteria": crit, "verdict": verdict}


def decide(rate, bs, aud):
    """Per backend: `rule` first; `rule-q` only if `rule` is not adopted. The headline verdict is
    FoundationModels'."""
    out = {}
    for b in BACKENDS:
        first = decide_variant(b, "rule", rate, bs, aud)
        second = decide_variant(b, "rule-q", rate, bs, aud)
        if first["verdict"] == "adopt (host stage)":
            final = "adopt (host stage): rule"
        elif second["verdict"] == "adopt (host stage)":
            final = "adopt (host stage): rule-q"
        else:
            final = first["verdict"]
        out[b] = {"rule": first, "rule-q": second, "verdict": final}
    return out


def hypotheses(rate, bs):
    return {
        "H1_fm_rule_absent_up_15_answer_down_at_most_5":
            bs[f"{FM}:rule:absent_rate"]["diff"] >= 0.15 and bs[f"{FM}:rule:answer_rate"]["diff"] >= -0.05,
        "H2_qwen_absent_gain_10_below_fm_gain":
            bs["qwen_gain_minus_fm_gain:rule:absent_rate"]["diff"] <= -0.10,
        "H3_reminder_adds_5_absent_for_fm_and_qwen":
            bs[f"{FM}:rule-q_minus_rule:absent_rate"]["diff"] >= 0.05
            and bs[f"{QWEN}:rule-q_minus_rule:absent_rate"]["diff"] >= 0.05,
    }


# --- Output ----------------------------------------------------------------------------------------

def pct(x):
    return "n/a" if x != x else f"{100 * x:.0f}%"


def pts(b):
    return f"{100 * b['diff']:+.1f} points, 95% CI [{100 * b['ci95'][0]:+.1f}, {100 * b['ci95'][1]:+.1f}]"


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
    raw = results / "raw"
    items = {it["item"]: it for it in load_jsonl(raw / "items.jsonl")}

    rows = {}
    for b in BACKENDS:
        for v in VARIANTS:
            rows[(b, v)] = [score(items[g["item"]], g) for g in load_jsonl(raw / f"gen-{b}-{v}.jsonl")]
            assert len(rows[(b, v)]) == len(items), f"{b} {v}: {len(rows[(b, v)])} of {len(items)} items"

    rate = {k: s6.rates(rs) for k, rs in rows.items()}
    rate_v1 = {k: s6.rates(as_v1(rs)) for k, rs in rows.items()}
    for k, rs in rows.items():
        rate[k]["fixed_phrase"] = sum(r["fixed_phrase"] for r in rs) / len(rs)
        rate[k]["fixed_phrase_answerable"] = sum(r["fixed_phrase"] for r in rs if r["answerable"]) \
            / sum(r["answerable"] for r in rs)
    bs = bootstrap_all(rows)
    aud = audit(results, rows, items)
    decision = decide(rate, bs, aud)
    hyp = hypotheses(rate, bs)

    # Does the base arm reproduce PoC 006's run 1? Same call on the same item, detector v1.
    repro = {}
    for b in BACKENDS:
        p = P6 / "results" / "raw" / f"gen-{b}-run1.jsonl"
        if p.exists():
            old = {g["item"]: s6.score(items[g["item"]], g)["call"] for g in load_jsonl(p)}
            new = {r["item"]: r["call_v1"] for r in rows[(b, "base")]}
            repro[b] = sum(old[i] == new[i] for i in old) / len(old)

    categories = sorted({it["category"] for it in items.values()})
    per_cat = {}
    for c in categories:
        per_cat[c] = {}
        for b in BACKENDS:
            for v in VARIANTS:
                rs = [r for r in rows[(b, v)] if r["category"] == c]
                ans = [r for r in rs if r["answerable"]]
                una = [r for r in rs if not r["answerable"]]
                per_cat[c][f"{b}:{v}"] = {
                    "answer_rate": sum(r["correct"] for r in ans) / len(ans) if ans else float("nan"),
                    "absent_rate": sum(r["correct"] for r in una) / len(una) if una else float("nan"),
                }

    summary = {
        "items": len(items),
        "contracts": len({it["contract"] for it in items.values()}),
        "arms": {f"{b}:{v}": rate[(b, v)] for b in BACKENDS for v in VARIANTS},
        "arms_detector_v1": {f"{b}:{v}": {k: rate_v1[(b, v)][k] for k in ("answer_rate", "absent_rate", "balanced")}
                             for b in BACKENDS for v in VARIANTS},
        "bootstrap": bs,
        "base_vs_poc006_run1_same_call": repro,
        "audit": aud,
        "hypotheses": hyp,
        "decision": decision,
        "per_category": per_cat,
    }
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    n_ans = rate[(FM, "base")]["answerable"]
    n_una = rate[(FM, "base")]["unanswerable"]
    lines = [
        "# PoC 008 summary",
        "",
        f"{len(items)} items ({n_ans} answerable, {n_una} unanswerable) from {summary['contracts']} contracts, "
        "one run per arm. Detector v2.",
        "",
        "| Backend | Variant | Answers answerable | Says absent on unanswerable | Balanced | Key fact right (n) "
        "| Any unsupported number | Fixed phrase, all | Fixed phrase, answerable | Hit cap | Errors | Median words | Median ms |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for b in BACKENDS:
        for v in VARIANTS:
            a = rate[(b, v)]
            errs = ", ".join(f"{k} {n}" for k, n in a["errors"].items()) or "0"
            lines.append(
                f"| {b} | {v} | {pct(a['answer_rate'])} | {pct(a['absent_rate'])} | **{pct(a['balanced'])}** "
                f"| {pct(a['key_fact'])} ({a['key_fact_n']}) | {pct(a['any_unsupported'])} "
                f"| {pct(a['fixed_phrase'])} | {pct(a['fixed_phrase_answerable'])} | {pct(a['cap'])} | {errs} "
                f"| {a['median_words']} | {a['median_ms']:.0f} |")
    lines += ["", "## Detector v1 (PoC 006's, frozen), for comparison", "",
              "| Backend | Variant | Answers answerable | Says absent on unanswerable | Balanced |", "|---|---|---|---|---|"]
    for b in BACKENDS:
        for v in VARIANTS:
            a = rate_v1[(b, v)]
            lines.append(f"| {b} | {v} | {pct(a['answer_rate'])} | {pct(a['absent_rate'])} | {pct(a['balanced'])} |")
    lines += ["", "## Changes against base (contract-level bootstrap, 10,000 resamples, seed 0)", ""]
    for b in BACKENDS:
        for v in TREATED:
            lines.append(f"**{b}, {v} minus base**")
            for m in ("balanced", "absent_rate", "answer_rate", "key_fact", "any_unsupported"):
                lines.append(f"- {m.replace('_', ' ')}: {pts(bs[f'{b}:{v}:{m}'])}")
            lines.append("")
    lines += ["**Placement and the Qwen-against-FoundationModels contrast**"]
    for name in ("fm:rule-q_minus_rule:absent_rate", "qwen-1.5b:rule-q_minus_rule:absent_rate",
                 "qwen_gain_minus_fm_gain:rule:absent_rate"):
        lines.append(f"- {name}: {pts(bs[name])}")
    lines += ["", "## Does base reproduce PoC 006 run 1? (same answer-or-absent call on the same item, detector v1)", ""]
    lines += [f"- {b}: {pct(v)}" for b, v in repro.items()] or ["- PoC 006 results not found"]
    lines += ["", "## Detector audit", ""]
    if aud is None:
        lines.append("Labels missing: fill in audit/labels.csv (a copy of audit/sheet.csv with the label column).")
    else:
        lines.append(f"- agreement: v2 {pct(aud['agreement'])}, v1 {pct(aud['agreement_v1'])} of {aud['labelled']} labelled "
                     "outputs; by backend (v2): " + ", ".join(f"{b} {pct(v)}" for b, v in aud["by_backend"].items())
                     + f"; without the {aud['fixed_phrase_outputs']} fixed-phrase outputs: "
                     + pct(aud["agreement_not_fixed_phrase"]))
    lines += ["", "## Per category, answers answerable / says absent on unanswerable", "",
              "| Category | " + " | ".join(f"{b}:{v}" for b in BACKENDS for v in VARIANTS) + " |",
              "|---|" + "---|" * (len(BACKENDS) * len(VARIANTS))]
    for c in categories:
        lines.append(f"| {c} | " + " | ".join(
            f"{pct(x['answer_rate'])} / {pct(x['absent_rate'])}" for x in per_cat[c].values()) + " |")
    lines += ["", "## Hypotheses", "", *[f"- {k}: {'holds' if v else 'does not hold'}" for k, v in hyp.items()],
              "", "## Decision rule (treated variant against base, per backend)", ""]
    for b in BACKENDS:
        for v in TREATED:
            d = decision[b][v]
            lines.append(f"- {b}, {v}: {d['verdict']} (" + ", ".join(
                f"{k.split('_')[0]} {'pass' if x else 'fail'}" for k, x in d["criteria"].items()) + ")")
    lines += ["", *[f"- {b}: **{decision[b]['verdict']}**" for b in BACKENDS],
              "", f"Headline verdict (FoundationModels): **{decision[FM]['verdict']}**", ""]
    (results / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
