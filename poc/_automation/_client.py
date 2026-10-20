"""Shared Anthropic client construction for the ideation pipeline LLM stages.

Single source of truth for how stages 2/3/4 build their `Anthropic` client, so
credentials, workspace scoping, and retry policy are configured in exactly one
place. No workspace ID is hardcoded — user-scoped keys (`sk-ant-usr-...`) require
ANTHROPIC_WORKSPACE_ID to be set in the environment.
"""
from __future__ import annotations

import os
import sys
from typing import Dict

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

    def add(self, usage) -> None:
        if not usage:
            return
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
