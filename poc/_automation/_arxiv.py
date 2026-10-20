"""Shared arXiv client.

arXiv's API terms require "no more than one request every three seconds, and
... a single connection at a time", counted across all your machines
(https://info.arxiv.org/help/api/tou.html). The `arxiv` library enforces its
inter-request `delay_seconds` per *client instance*, so the keyword search and
the semantic arm must share ONE client — otherwise their two independent timers
can fire closer together than 3s and get the IP blocked (429), which is what
happened. `num_retries` is kept low on purpose: retrying into an active 429 just
hammers the block and extends it; callers catch the error and degrade to [].
"""
from __future__ import annotations

_client = None


def get_client():
    """Process-wide singleton arxiv.Client, lazily constructed."""
    global _client
    if _client is None:
        import arxiv
        _client = arxiv.Client(
            page_size=200,     # pools up to 200 in a single request
            delay_seconds=3.0,  # arXiv's documented minimum
            num_retries=2,      # don't hammer a 429; caller degrades gracefully
        )
    return _client
