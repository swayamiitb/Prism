"""
Slack Context Provider
======================

Day-to-day company know-how lives in Slack. This provider searches historical
threads ("how do we handle X?" conversations, incident retros) and returns them
with full provenance (channel, timestamp, permalink) so the Brain can cite them.

Default backend: seeded JSONL data (``data/northwind/slack.jsonl``) so the Brain
runs with zero credentials. Set ``SLACK_BOT_TOKEN`` to switch to a real workspace
(future; the search contract stays identical).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from context_brain.providers.base import Answer, ContextProvider, Document, Status

log = logging.getLogger(__name__)

DEFAULT_SLACK_PATH = Path(__file__).resolve().parents[2] / "data" / "northwind" / "slack.jsonl"


def _slack_path() -> Path:
    import os

    return Path(os.environ.get("SLACK_PATH", str(DEFAULT_SLACK_PATH)))


class SlackProvider(ContextProvider):
    """Search historical Slack threads (seeded data by default)."""

    id = "slack"
    name = "Slack (threads/channels)"

    def __init__(self) -> None:
        self.path = _slack_path()
        self._threads: list[dict[str, Any]] = []
        self._loaded = False

    def _load(self) -> list[dict[str, Any]]:
        if self._loaded:
            return self._threads
        if self.path.exists():
            try:
                with self.path.open(encoding="utf-8") as f:
                    self._threads = [json.loads(line) for line in f if line.strip()]
            except OSError as exc:
                log.warning("slack load failed: %s", exc)
        self._loaded = True
        return self._threads

    # ── Health ─────────────────────────────────────────────────────────────
    def status(self) -> Status:
        import os

        if os.environ.get("SLACK_BOT_TOKEN"):
            return Status(ok=True, detail="real Slack workspace (token set)")
        threads = self._load()
        if not threads:
            return Status(ok=False, detail=f"no seeded threads at {self.path}")
        channels = {t.get("channel") for t in threads}
        return Status(ok=True, detail=f"seeded: {len(threads)} threads across {len(channels)} channel(s)")

    # ── Read ───────────────────────────────────────────────────────────────
    def query(self, question: str) -> Answer:
        threads = self._load()
        if not threads:
            return Answer(text="No Slack threads available (no seeded data and no SLACK_BOT_TOKEN).")
        terms = _extract_terms(question)
        scored: list[tuple[int, dict[str, Any]]] = []
        for t in threads:
            haystack = (
                t.get("topic", "")
                + " "
                + t.get("text", "")
                + " "
                + " ".join(m.get("text", "") for m in t.get("replies", []))
            ).lower()
            score = sum(haystack.count(w) for w in terms)
            if score > 0:
                scored.append((score, t))
        if not scored:
            return Answer(text=f"No Slack threads match {question!r}.")
        scored.sort(key=lambda s: s[0], reverse=True)
        docs = [_thread_doc(t) for _, t in scored[:6]]
        top = scored[0][1]
        return Answer(
            text=f"{len(scored)} thread(s) match. Top: #{top.get('channel')} '{top.get('topic')}'.", results=docs
        )


def _extract_terms(question: str) -> list[str]:
    words = re.findall(r"[a-z0-9-]+", question.lower())
    stop = {
        "the",
        "a",
        "an",
        "how",
        "do",
        "does",
        "we",
        "our",
        "is",
        "are",
        "to",
        "of",
        "in",
        "on",
        "for",
        "and",
        "or",
        "what",
        "who",
        "tell",
        "me",
        "about",
        "handle",
        "handled",
    }
    return [w for w in words if w not in stop and len(w) > 2]


def _thread_doc(t: dict[str, Any]) -> Document:
    replies = t.get("replies", [])
    snippet = t.get("text", "")
    if replies:
        snippet += "\n" + "\n".join(f"  > {r.get('user', '?')}: {r.get('text', '')}" for r in replies[:3])
    return Document(
        id=str(t.get("ts", t.get("channel", ""))),
        name=f"#{t.get('channel', '?')} — {t.get('topic', '(thread)')}",
        uri=t.get("permalink", ""),
        source="slack",
        snippet=snippet[:500],
        raw={
            "channel": t.get("channel"),
            "ts": t.get("ts"),
            "author": t.get("user"),
            "reply_count": len(replies),
        },
    )
