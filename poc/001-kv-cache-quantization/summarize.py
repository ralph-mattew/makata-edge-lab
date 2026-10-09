#!/usr/bin/env python3
"""Summarize PoC 001 raw logs into summary.json and summary.md.

Usage: python3 summarize.py [RESULTS_DIR]   (default: results/ next to this script)
Reads RESULTS_DIR/raw/ and writes RESULTS_DIR/summary.json and RESULTS_DIR/summary.md.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
RESULTS = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "results"
RAW = RESULTS / "raw"
ARMS = ["f16-nofa", "f16-fa", "q8k-nofa", "q8-fa", "q4-fa"]
MIB = 1024 * 1024


def floats(pattern, text):
    return [float(m) for m in re.findall(pattern, text)]


def context_memory(segment):
    """KV and compute buffers of one llama_context, from the llama.cpp log."""
    kv = floats(r"KV buffer size\s*=\s*([\d.]+) MiB", segment)
    cells = re.search(r"llama_context: n_ctx\s*=\s*(\d+)", segment)
    return {
        "n_ctx": int(cells.group(1)) if cells else None,
        "kv_global_mib": kv[0] if kv else None,
        "kv_swa_mib": kv[1] if len(kv) > 1 else None,
        "kv_mib": round(sum(kv), 2),
        "compute_mib": round(sum(floats(r"sched_reserve:\s+\S+ compute buffer size\s*=\s*([\d.]+) MiB", segment)), 2),
    }


def bench(arm, ctx):
    log = RAW / f"bench-{arm}-{ctx}.log"
    js = RAW / f"bench-{arm}-{ctx}.json"
    if not log.exists():
        return None
    text = log.read_text(errors="replace")
    # llama-bench builds one context per test: prefill (p + d cells, padded) then decode (n + d).
    segments = text.split("constructing llama_context")[1:]
    row = context_memory(segments[0]) if segments else {"kv_mib": 0.0, "compute_mib": 0.0}
    row["decode_context"] = context_memory(segments[1]) if len(segments) > 1 else None
    gpu_model = floats(r"MTL0_Mapped model buffer size\s*=\s*([\d.]+) MiB", text)
    row["model_gpu_mib"] = gpu_model[0] if gpu_model else None
    fp = re.search(r"(\d+)\s+peak memory footprint", text)
    rss = re.search(r"(\d+)\s+maximum resident set size", text)
    row["peak_footprint_mib"] = round(int(fp.group(1)) / MIB, 1) if fp else None
    row["max_rss_mib"] = round(int(rss.group(1)) / MIB, 1) if rss else None
    try:
        tests = json.loads(js.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        tests = []
    for t in tests:
        key = "prefill" if t.get("n_prompt", 0) > 0 else "decode"
        row[f"{key}_tps"] = round(t["avg_ts"], 2)
        row[f"{key}_tps_sd"] = round(t["stddev_ts"], 2)
        row["depth"] = t.get("n_depth")
    row["ok"] = bool(tests)
    return row


def kld(arm, ctx):
    log = RAW / f"kld-{arm}-{ctx}.log"
    if not log.exists():
        return None
    text = log.read_text(errors="replace")

    def pm(label):
        m = re.search(label + r"\s*:\s*([-\d.]+)\s*±\s*([\d.]+)", text)
        return (float(m.group(1)), float(m.group(2))) if m else (None, None)

    k, k_se = pm(r"Mean\s+KLD")
    top, top_se = pm(r"Same top p")
    ppl, ppl_se = pm(r"Mean PPL\(Q\)")
    base_ppl, _ = pm(r"Mean PPL\(base\)")
    return {"mean_kld": k, "mean_kld_se": k_se, "same_top_pct": top, "same_top_pct_se": top_se,
            "ppl": ppl, "ppl_se": ppl_se, "ppl_base": base_ppl, "ok": k is not None}


def main():
    out = {"conditions": {}, "bench": {}, "kld": {}}
    cond = RAW / "conditions.txt"
    if cond.exists():
        out["conditions"] = dict(l.split("=", 1) for l in cond.read_text().splitlines() if "=" in l)
    for arm in ARMS:
        out["bench"][arm] = {str(c): bench(arm, c) for c in (2048, 4096, 8192)}
        out["kld"][arm] = {str(c): kld(arm, c) for c in (2048, 4096)}
    (RESULTS / "summary.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    lines = ["| Arm | Context | KV MiB | Compute MiB | KV + compute MiB | Peak footprint MiB | Prefill tok/s | Decode tok/s |",
             "|---|---|---|---|---|---|---|---|"]
    for arm in ARMS:
        for c, r in out["bench"][arm].items():
            if not r:
                continue
            lines.append(
                f"| {arm} | {c} | {r['kv_mib']:.2f} | {r['compute_mib']:.2f} | {r['kv_mib'] + r['compute_mib']:.2f} | "
                f"{r['peak_footprint_mib']} | {r.get('prefill_tps', '-')} ± {r.get('prefill_tps_sd', '-')} | "
                f"{r.get('decode_tps', '-')} ± {r.get('decode_tps_sd', '-')} |")
    lines += ["", "| Arm | Context | Mean KLD | Same top token % | PPL |", "|---|---|---|---|---|"]
    for arm in ARMS:
        for c, r in out["kld"][arm].items():
            if not r or not r["ok"]:
                continue
            lines.append(f"| {arm} | {c} | {r['mean_kld']:.6f} ± {r['mean_kld_se']:.6f} | "
                         f"{r['same_top_pct']:.2f} ± {r['same_top_pct_se']:.2f} | {r['ppl']:.2f} ± {r['ppl_se']:.2f} |")
    md = "\n".join(lines) + "\n"
    (RESULTS / "summary.md").write_text(md)
    print(md, end="")


if __name__ == "__main__":
    main()
