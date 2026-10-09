"""PoC 006 scoring: answer-or-absent calls, key facts, unsupported numbers, the decision rule.

Usage: python3 summarize.py [RESULTS_DIR]   (default: results)

Reads RESULTS_DIR/raw/items.jsonl and RESULTS_DIR/raw/gen-<arm>-run<k>.jsonl. Writes
RESULTS_DIR/summary.json and RESULTS_DIR/summary.md. On the first call it also writes the blinded
audit sheet, RESULTS_DIR/audit/sheet.csv, and its key, RESULTS_DIR/audit/key.json. Once
RESULTS_DIR/audit/labels.csv exists, the detector's agreement with it is part of the summary.
"""

import csv
import json
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from facts import dates, durations, jurisdictions

HERE = Path(__file__).resolve().parent
ARMS = ["fm", "gemma-e2b", "qwen-1.5b"]
FM, GEMMA, QWEN = ARMS
BOOTSTRAP_RESAMPLES = 10_000
AUDIT_PER_ARM = 40
AUDIT_MIN_AGREEMENT = 0.90
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

# --- Output cleanup, as the app does before showing an answer ---------------------------------

GEMMA_BLOCKS = [r"<\|channel>[\s\S]*?<channel\|>", r"<\|tool_call>[\s\S]*?<tool_call\|>",
                r"<\|tool_response>[\s\S]*?<tool_response\|>"]
GEMMA_TOKENS = ["<|channel>", "<channel|>", "<|think|>", "<|turn>", "<turn|>", "<|tool_call>",
                "<tool_call|>", "<|tool_response>", "<tool_response|>"]


def clean(arm, text):
    if arm == GEMMA:
        for p in GEMMA_BLOCKS:
            text = re.sub(p, "", text)
        for t in GEMMA_TOKENS:
            text = text.replace(t, "")
    elif arm == QWEN:
        text = re.sub(r"<think>[\s\S]*?</think>", "", text)
        text = text.split("<think>")[0]
    return text.strip()


# --- The answer-or-absent detector (frozen at registration) -----------------------------------
# An output is "absent" when its first sentence says the documents do not contain the answer,
# or answers no. Everything else that is not empty is an "answer".

ABSENT = [re.compile(p) for p in [
    r"^(no|none|nope)\b",
    r"\b(does not|doesn't|do not|don't|did not|didn't|is not|isn't|are not|aren't|was not|wasn't)\b"
    r"[^.]{0,80}?\b(mention|specify|state|say|include|contain|provide|address|indicate|give|list|"
    r"define|detail|discuss|reference|describe|cover|outline|set out|appear)",
    r"\bno (mention|information|reference|details?|indication|provision|clause|specific|explicit|"
    r"statement|data|record)\b",
    r"\bnot (mentioned|specified|stated|provided|included|addressed|indicated|found|available|"
    r"given|listed|defined|clear|described|discussed|covered|present|specific)\b",
    r"\bthere (is|are) no\b",
    r"\b(cannot|can't|can not|could not|couldn't|unable to)\b[^.]{0,30}?\b(determine|answer|find|"
    r"tell|identify|confirm|provide|say|be answered|be determined)\b",
    r"\b(nothing|none) (in|of) the (provided |given )?(document|sections?|text|contract|agreement)",
]]


def first_sentence(text):
    text = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s+", "", text.strip())
    m = re.search(r"(?<=[.!?])\s|\n", text)
    return (text[: m.start()] if m else text).strip().lower().replace("’", "'")


def call(text):
    """"absent", "answer" or "empty"."""
    if not text.strip():
        return "empty"
    s = first_sentence(text)
    return "absent" if any(p.search(s) for p in ABSENT) else "answer"


# --- Measures -----------------------------------------------------------------------------------

def numbers(text):
    found = set()
    for raw in NUMBER.findall(text):
        n = raw.replace(",", "").rstrip(".")
        if sum(ch.isdigit() for ch in n) >= 2:
            found.add(n)
    return found


def facts_in(kind, text):
    if kind == "date":
        return {("date", *f) for f in dates(text)}
    if kind == "duration":
        return {("duration", *f) for f in durations(text)}
    if kind == "date_or_duration":
        return facts_in("date", text) | facts_in("duration", text)
    return {("jurisdiction", j) for j in jurisdictions(text)}


def score(item, gen):
    error = gen["stop"] in ("error", "prompt_too_long", "decode_error")
    text = "" if error else clean(gen["arm"], gen["text"])
    c = "error" if error else call(text)
    unsupported = sorted(numbers(text) - numbers(item["source"]))
    row = {
        "item": item["item"],
        "contract": item["contract"],
        "category": item["category"],
        "answerable": item["answerable"],
        "call": c,
        # correct: answers an answerable item, or says absent on an unanswerable one
        "correct": (c == "answer") if item["answerable"] else (c == "absent"),
        "any_unsupported": bool(unsupported),
        "unsupported": unsupported,
        "cap": gen["stop"] == "cap" or (gen.get("response_tokens") or 0) >= 495,
        "error": gen.get("error") or (gen["stop"] if error else None),
        "words": len(text.split()),
        "ms": gen.get("total_ms") or (gen.get("prefill_ms", 0) + gen.get("generate_ms", 0)),
        "text": text,
    }
    if item["answerable"] and item["key_facts"]:
        gold = {tuple(f) for f in item["key_facts"]}
        row["key_fact"] = bool(gold & facts_in(item["key_fact_kind"], text))
    return row


def rates(rows):
    ans = [r for r in rows if r["answerable"]]
    una = [r for r in rows if not r["answerable"]]
    kf = [r for r in rows if "key_fact" in r]
    answer_rate = sum(r["correct"] for r in ans) / len(ans)
    absent_rate = sum(r["correct"] for r in una) / len(una)
    return {
        "n": len(rows),
        "answerable": len(ans),
        "unanswerable": len(una),
        "answer_rate": answer_rate,
        "absent_rate": absent_rate,
        "balanced": (answer_rate + absent_rate) / 2,
        "gap_filled": 1 - absent_rate,
        "absent_on_answerable": sum(r["call"] == "absent" for r in ans) / len(ans),
        "key_fact_n": len(kf),
        "key_fact": sum(r["key_fact"] for r in kf) / len(kf) if kf else float("nan"),
        "any_unsupported": sum(r["any_unsupported"] for r in rows) / len(rows),
        "any_unsupported_unanswerable": sum(r["any_unsupported"] for r in una) / len(una),
        "cap": sum(r["cap"] for r in rows) / len(rows),
        "errors": dict(Counter(r["error"] for r in rows if r["error"])),
        "empty": sum(r["call"] == "empty" for r in rows),
        "median_words": statistics.median(r["words"] for r in rows),
        "median_ms": statistics.median(r["ms"] for r in rows),
    }


MEASURES = {
    "balanced": lambda rs: rates(rs)["balanced"],
    "absent_rate": lambda rs: rates(rs)["absent_rate"],
    "answer_rate": lambda rs: rates(rs)["answer_rate"],
    "any_unsupported": lambda rs: rates(rs)["any_unsupported"],
}


def bootstrap(rows_by_arm, measure, hi, lo):
    """Contract-level bootstrap of measure(hi) - measure(lo): contracts are resampled with
    replacement, with all their items. 10,000 resamples, seed 0."""
    contracts = sorted({r["contract"] for r in rows_by_arm[hi]})
    # Per contract and arm: [answerable, answered, unanswerable, said absent, key-fact items,
    # key fact right, items, any unsupported]
    agg = {arm: defaultdict(lambda: [0] * 8) for arm in (hi, lo)}
    for arm in (hi, lo):
        for r in rows_by_arm[arm]:
            a = agg[arm][r["contract"]]
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

    def div(x, y):
        return x / y if y else float("nan")

    def value(arm, sample):
        t = [0] * 8
        for c in sample:
            for i, v in enumerate(agg[arm][c]):
                t[i] += v
        a, u = div(t[1], t[0]), div(t[3], t[2])
        return {"balanced": (a + u) / 2, "answer_rate": a, "absent_rate": u,
                "key_fact": div(t[5], t[4]), "any_unsupported": div(t[7], t[6])}[measure]

    rng = random.Random(0)
    draws = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = [rng.choice(contracts) for _ in contracts]
        d = value(hi, sample) - value(lo, sample)
        if d == d:  # skip NaN
            draws.append(d)
    draws.sort()
    k = len(draws)
    return {"diff": value(hi, contracts) - value(lo, contracts),
            "ci95": [draws[int(0.025 * k)], draws[int(0.975 * k) - 1]]}


# --- Audit ------------------------------------------------------------------------------------

def audit(results, rows_by_arm, items):
    """Blinded audit of the detector: AUDIT_PER_ARM run-1 outputs per arm, shuffled, with no arm
    and no detector call on the sheet. Returns agreement once labels.csv exists."""
    folder = results / "audit"
    sheet, key_path, labels = folder / "sheet.csv", folder / "key.json", folder / "labels.csv"
    if not sheet.exists():
        folder.mkdir(exist_ok=True)
        rng = random.Random(0)
        picks = []
        for arm in ARMS:
            for r in rng.sample(rows_by_arm[arm], AUDIT_PER_ARM):
                if r["call"] not in ("error", "empty"):
                    picks.append((arm, r))
        rng.shuffle(picks)
        with open(sheet, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["id", "question", "answer", "label (answer / absent)"])
            for n, (arm, r) in enumerate(picks):
                w.writerow([n, items[r["item"]]["question"], r["text"], ""])
        key_path.write_text(json.dumps(
            [{"id": n, "arm": arm, "item": r["item"], "call": r["call"]} for n, (arm, r) in enumerate(picks)],
            indent=1) + "\n")
    if not labels.exists():
        return None
    key = {k["id"]: k for k in json.loads(key_path.read_text())}
    with open(labels, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.reader(f)][1:]
    labelled = [(key[int(r[0])], r[3].strip().lower()) for r in rows if r[3].strip()]
    agree = sum(k["call"] == lab for k, lab in labelled)
    by_arm = {arm: [(k, lab) for k, lab in labelled if k["arm"] == arm] for arm in ARMS}
    return {
        "labelled": len(labelled),
        "agreement": agree / len(labelled) if labelled else float("nan"),
        "by_arm": {a: sum(k["call"] == lab for k, lab in v) / len(v) for a, v in by_arm.items() if v},
        "disagreements": [{"id": k["id"], "arm": k["arm"], "item": k["item"], "detector": k["call"], "label": lab}
                          for k, lab in labelled if k["call"] != lab],
    }


# --- Decision ---------------------------------------------------------------------------------

def decide(s, bs, aud):
    """Gemma E2B vs FoundationModels on the 8 GB tier. First match wins."""
    g, f = s[GEMMA], s[FM]
    gain = bs["balanced_gemma_minus_fm"]
    crit = {
        "c0_detector_agreement_at_least_90": aud is not None and aud["agreement"] >= AUDIT_MIN_AGREEMENT,
        "c1_balanced_gain_at_least_10_ci_above_0": gain["diff"] >= 0.10 and gain["ci95"][0] > 0,
        "c2_key_fact_not_worse_than_minus_5": g["key_fact"] >= f["key_fact"] - 0.05,
        "c3_unsupported_not_worse_than_plus_5": g["any_unsupported"] <= f["any_unsupported"] + 0.05,
    }
    if aud is None:
        verdict = "pending: audit labels missing"
    elif not crit["c0_detector_agreement_at_least_90"]:
        verdict = "inconclusive: detector not valid"
    elif gain["diff"] < 0.05:
        verdict = "reject: no gain"
    elif all(crit.values()):
        verdict = "adopt (host stage)"
    elif crit["c1_balanced_gain_at_least_10_ci_above_0"]:
        verdict = "reject: trade-off"
    else:
        verdict = "inconclusive"
    return {"criteria": crit, "verdict": verdict}


def hypotheses(s):
    q, g, f = s[QWEN], s[GEMMA], s[FM]
    return {
        "H1_qwen_absent_rate_15_below_fm_and_gemma":
            q["absent_rate"] <= f["absent_rate"] - 0.15 and q["absent_rate"] <= g["absent_rate"] - 0.15,
        "H2_qwen_unsupported_5_above_fm_and_gemma":
            q["any_unsupported"] >= f["any_unsupported"] + 0.05 and q["any_unsupported"] >= g["any_unsupported"] + 0.05,
        "H3_fm_gemma_balanced_within_10": abs(g["balanced"] - f["balanced"]) <= 0.10,
    }


def load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pct(x):
    return "n/a" if x != x else f"{100 * x:.0f}%"


def ci_line(label, b):
    return f"- {label}: {100 * b['diff']:+.1f} points, 95% CI [{100 * b['ci95'][0]:+.1f}, {100 * b['ci95'][1]:+.1f}]"


def main():
    results = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
    raw = results / "raw"
    items = {it["item"]: it for it in load_jsonl(raw / "items.jsonl")}

    rows = {}
    rerun = {}
    for arm in ARMS:
        rows[arm] = [score(items[g["item"]], g) for g in load_jsonl(raw / f"gen-{arm}-run1.jsonl")]
        p2 = raw / f"gen-{arm}-run2.jsonl"
        if p2.exists():
            second = {g["item"]: score(items[g["item"]], g)["call"] for g in load_jsonl(p2)}
            first = {r["item"]: r["call"] for r in rows[arm]}
            common = sorted(set(first) & set(second))
            rerun[arm] = {"items": len(common),
                          "same_call": sum(first[i] == second[i] for i in common) / len(common)}
        assert len(rows[arm]) == len(items), f"{arm}: {len(rows[arm])} of {len(items)} items"

    s = {arm: rates(rows[arm]) for arm in ARMS}
    bs = {
        "balanced_gemma_minus_fm": bootstrap(rows, "balanced", GEMMA, FM),
        "key_fact_gemma_minus_fm": bootstrap(rows, "key_fact", GEMMA, FM),
        "unsupported_gemma_minus_fm": bootstrap(rows, "any_unsupported", GEMMA, FM),
        "absent_rate_qwen_minus_fm": bootstrap(rows, "absent_rate", QWEN, FM),
        "absent_rate_qwen_minus_gemma": bootstrap(rows, "absent_rate", QWEN, GEMMA),
        "unsupported_qwen_minus_fm": bootstrap(rows, "any_unsupported", QWEN, FM),
        "unsupported_qwen_minus_gemma": bootstrap(rows, "any_unsupported", QWEN, GEMMA),
    }
    aud = audit(results, rows, items)
    decision = decide(s, bs, aud)
    hyp = hypotheses(s)

    categories = sorted({it["category"] for it in items.values()})
    per_cat = {}
    for c in categories:
        per_cat[c] = {}
        for arm in ARMS:
            rs = [r for r in rows[arm] if r["category"] == c]
            ans = [r for r in rs if r["answerable"]]
            una = [r for r in rs if not r["answerable"]]
            kf = [r["key_fact"] for r in rs if "key_fact" in r]
            per_cat[c][arm] = {
                "answer_rate": sum(r["correct"] for r in ans) / len(ans) if ans else float("nan"),
                "absent_rate": sum(r["correct"] for r in una) / len(una) if una else float("nan"),
                "key_fact": sum(kf) / len(kf) if kf else float("nan"),
            }

    summary = {
        "items": len(items),
        "contracts": len({it["contract"] for it in items.values()}),
        "arms": s,
        "bootstrap": bs,
        "rerun_agreement": rerun,
        "audit": aud,
        "hypotheses": hyp,
        "decision": decision,
        "per_category": per_cat,
    }
    (results / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    lines = [
        "# PoC 006 summary",
        "",
        f"{len(items)} items ({s[FM]['answerable']} answerable, {s[FM]['unanswerable']} unanswerable) "
        f"from {summary['contracts']} contracts. Run 1 of each arm.",
        "",
        "| Arm | Answers answerable | Says absent on unanswerable | Balanced | Key fact right (n) | Any unsupported number | Unsupported, unanswerable | Hit cap | Errors | Median words | Median ms |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for arm in ARMS:
        a = s[arm]
        errs = ", ".join(f"{k} {v}" for k, v in a["errors"].items()) or "0"
        lines.append(
            f"| {arm} | {pct(a['answer_rate'])} | {pct(a['absent_rate'])} | **{pct(a['balanced'])}** "
            f"| {pct(a['key_fact'])} ({a['key_fact_n']}) | {pct(a['any_unsupported'])} "
            f"| {pct(a['any_unsupported_unanswerable'])} | {pct(a['cap'])} | {errs} "
            f"| {a['median_words']} | {a['median_ms']:.0f} |")
    lines += ["", "Contract-level bootstrap (10,000 resamples, seed 0):", ""]
    lines += [ci_line(k.replace("_", " "), v) for k, v in bs.items()]
    lines += ["", "## Run-to-run agreement (same call in run 1 and run 2)", ""]
    lines += [f"- {arm}: {pct(v['same_call'])} of {v['items']} items" for arm, v in rerun.items()] or ["- no run 2 files"]
    lines += ["", "## Detector audit", ""]
    if aud is None:
        lines.append("Labels missing: fill in audit/labels.csv (a copy of audit/sheet.csv with the label column).")
    else:
        lines.append(f"- agreement: {pct(aud['agreement'])} of {aud['labelled']} labelled outputs "
                     + ", ".join(f"{a} {pct(v)}" for a, v in aud["by_arm"].items()))
    lines += ["", "## Per category (answers answerable / says absent on unanswerable / key fact)", "",
              "| Category | " + " | ".join(ARMS) + " |", "|---|" + "---|" * len(ARMS)]
    for c in categories:
        cells = [f"{pct(v['answer_rate'])} / {pct(v['absent_rate'])} / {pct(v['key_fact'])}" for v in per_cat[c].values()]
        lines.append(f"| {c} | " + " | ".join(cells) + " |")
    lines += ["", "## Hypotheses", "", *[f"- {k}: {'holds' if v else 'does not hold'}" for k, v in hyp.items()],
              "", "## Decision rule (gemma-e2b vs fm)", "",
              *[f"- {k}: {'pass' if v else 'fail'}" for k, v in decision["criteria"].items()],
              "", f"Verdict: **{decision['verdict']}**", ""]
    (results / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
