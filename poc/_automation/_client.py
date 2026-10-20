"""Shared Anthropic client construction for the ideation pipeline LLM stages.

Single source of truth for how stages 2/3/4 build their `Anthropic` client, so
credentials, workspace scoping, and retry policy are configured in exactly one
place. No workspace ID is hardcoded — user-scoped keys (`sk-ant-usr-...`) require
ANTHROPIC_WORKSPACE_ID to be set in the environment.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional

from anthropic import Anthropic


def make_client(config: Dict) -> Anthropic:
    """Build an Anthropic client from config + environment.

    - API key comes from the env var named by `config['llm']['api_key_env']`.
    - User-scoped keys additionally need ANTHROPIC_WORKSPACE_ID (no default; a
      baked-in workspace ID must never be committed to a public repo).
    - `config['llm']['max_retries']` (optional) tunes the SDK's automatic
      429/5xx exponential backoff; defaults to 2 (the SDK default).
    """
    api_key_env = config["llm"]["api_key_env"]
    api_key = os.getenv(api_key_env)
    if not api_key:
        sys.exit(f"Error: {api_key_env} environment variable not set "
                 f"(export {api_key_env}=your-api-key)")

    kwargs = {"api_key": api_key, "max_retries": int(config["llm"].get("max_retries", 2))}

    # User-scoped keys must be pinned to a workspace via header. Require it
    # explicitly rather than shipping someone's workspace ID in the source.
    if api_key.startswith("sk-ant-usr-"):
        workspace_id = os.getenv("ANTHROPIC_WORKSPACE_ID")
        if not workspace_id:
            sys.exit("Error: user-scoped API key detected (sk-ant-usr-...) but "
                     "ANTHROPIC_WORKSPACE_ID is not set. Export it, or use a "
                     "workspace/organization key.")
        kwargs["default_headers"] = {"anthropic-workspace-id": workspace_id}

    return Anthropic(**kwargs)


def resolve_model(config: Dict, stage: str) -> str:
    """Model for a stage: `llm.models[stage]` if set, else the global `llm.model`.

    Lets the cheap, high-volume relevance filter run on Haiku while extraction
    and the quality gates use a stronger model, without forking the config.
    """
    per_stage = (config.get("llm", {}).get("models") or {})
    return per_stage.get(stage, config["llm"]["model"])


# Per-MTok (input, output) list pricing — used only for a rough run-cost estimate
# in the logs. Cache reads bill ~0.1x input; cache writes ~1.25x input.
_PRICING = {
    "claude-opus-4-8": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-5": (3.0, 15.0),
}


def _price_for(model: str):
    for key, px in _PRICING.items():
        if model.startswith(key):
            return px
    return None


class CostTracker:
    """Accumulates token usage across a stage's LLM calls and estimates cost."""

    def __init__(self, model: str):
        self.model = model
        self.input = 0
        self.output = 0
        self.cache_read = 0
        self.cache_write = 0
        self._lock = threading.Lock()

    def add(self, usage) -> None:
        if not usage:
            return
        with self._lock:  # called from worker threads under concurrency
            self.input += getattr(usage, "input_tokens", 0) or 0
            self.output += getattr(usage, "output_tokens", 0) or 0
            self.cache_read += getattr(usage, "cache_read_input_tokens", 0) or 0
            self.cache_write += getattr(usage, "cache_creation_input_tokens", 0) or 0

    def estimate_usd(self):
        px = _price_for(self.model)
        if not px:
            return None
        in_px, out_px = px
        return (
            self.input * in_px
            + self.cache_read * in_px * 0.1
            + self.cache_write * in_px * 1.25
            + self.output * out_px
        ) / 1_000_000

    def summary(self) -> str:
        usd = self.estimate_usd()
        cost = f"~${usd:.3f}" if usd is not None else "n/a"
        return (f"tokens: in={self.input} out={self.output} "
                f"cache_read={self.cache_read} cache_write={self.cache_write} "
                f"| est cost {cost} ({self.model})")


# ---------------------------------------------------------------------------
# Prompt loading + LLM call
# ---------------------------------------------------------------------------
_PROMPTS_DIR = Path(__file__).parent / "prompts"
_USER_MARKER = "===USER==="


def load_split_prompt(name: str):
    """Load a prompt template split into (system, user) halves on `===USER===`.

    The system half is the stable, per-run-identical instructions + context (so
    it can be cached across items); the user half is the volatile per-item data.
    Templates without the marker fall back to (None, whole-template).
    """
    text = (_PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")
    if _USER_MARKER in text:
        sys_part, user_part = text.split(_USER_MARKER, 1)
        return sys_part.strip(), user_part.strip()
    return None, text


def _extract_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
    return None


def call_json(client, model: str, system_text: Optional[str], user_text: str,
              max_tokens: int, tracker: CostTracker, schema: Optional[dict] = None) -> Optional[dict]:
    """One Messages call that returns parsed JSON (or None).

    - `system_text` is sent as a cached system block (`cache_control: ephemeral`).
      NOTE: caching only engages once that block exceeds the model's minimum
      cacheable prefix (~2048 tok Sonnet 4.6 / ~4096 tok Haiku 4.5); smaller
      prefixes silently don't cache — harmless, just no hit.
    - `schema`, when given, constrains output via structured outputs
      (`output_config.format`); falls back to prompt-guided JSON on older SDKs.
    """
    kwargs = dict(model=model, max_tokens=max_tokens,
                  messages=[{"role": "user", "content": user_text}])
    if system_text:
        kwargs["system"] = [{"type": "text", "text": system_text,
                             "cache_control": {"type": "ephemeral"}}]

    if schema is not None:
        try:
            resp = client.messages.create(
                output_config={"format": {"type": "json_schema", "schema": schema}},
                **kwargs,
            )
        except TypeError:
            # SDK without output_config — rely on the prompt's JSON instructions.
            resp = client.messages.create(**kwargs)
    else:
        resp = client.messages.create(**kwargs)

    tracker.add(getattr(resp, "usage", None))
    text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
    return _extract_json(text)


def concurrent_map(fn: Callable, items: List, workers: int) -> List:
    """`[fn(x) for x in items]`, parallelized across `workers` threads (order
    preserved). Caching caveat: a cache entry is only readable after the first
    response starts streaming, so when the shared system prefix is large enough
    to cache, prefer a warmup call before fanning out. At current prompt sizes
    the prefix is sub-minimum (no caching), so plain fan-out is fine."""
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, items))
