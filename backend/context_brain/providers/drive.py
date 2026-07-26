"""
Drive Context Provider
======================

Company docs — design docs, process docs, spreadsheets — pulled from Google
Drive (or, by default, seeded local docs under ``data/northwind/drive/``). Read-
only: the Brain reads docs and synthesizes their content into the graph via
``update_brain``; it does not write back to Drive.

Set ``GOOGLE_SERVICE_ACCOUNT_FILE`` to switch to a real Drive (future; the read
contract stays identical).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from context_brain.providers.base import Answer, ContextProvider, Document, Status

log = logging.getLogger(__name__)

DEFAULT_DRIVE_PATH = Path(__file__).resolve().parents[2] / "data" / "northwind" / "drive"


def _drive_root() -> Path:
    import os

    return Path(os.environ.get("DRIVE_PATH", str(DEFAULT_DRIVE_PATH)))


class DriveProvider(ContextProvider):
    """Search company docs (seeded local markdown by default)."""

    id = "drive"
    name = "Google Drive / docs"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _drive_root()

    # ── Health ─────────────────────────────────────────────────────────────
    def status(self) -> Status:
        import os

        if os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE"):
            return Status(ok=True, detail="real Google Drive (service account set)")
        if not self.root.exists():
            return Status(ok=False, detail=f"drive path missing: {self.root}")
        docs = list(self.root.rglob("*.md"))
        return Status(ok=True, detail=f"seeded: {len(docs)} doc(s) at {self.root}")

    # ── Read ───────────────────────────────────────────────────────────────
    def query(self, question: str) -> Answer:
        if not self.root.exists():
            return Answer(text=f"Drive not found at {self.root}.")
        terms = _extract_terms(question)
        hits: list[tuple[int, Path, str, str]] = []
        for doc in self.root.rglob("*.md"):
            try:
                text = doc.read_text(encoding="utf-8")
            except OSError:
                continue
            lower = text.lower()
            score = sum(lower.count(t) for t in terms)
            title = _title_of(text, doc)
            score += 3 * sum(t in title.lower() for t in terms)
            if score > 0:
                snippet = _snippet_for(text, terms) or text[:200]
                hits.append((score, doc, title, snippet))
        if not hits:
            return Answer(text=f"No Drive docs match {question!r}.")
        hits.sort(key=lambda h: h[0], reverse=True)
        docs = [
            Document(
                id=str(p),
                name=title,
                uri=f"drive://northwind/{p.name}",
                source="drive",
                snippet=snip[:400],
            )
            for _, p, title, snip in hits[:6]
        ]
        return Answer(text=f"{len(hits)} doc(s) match. Top: {hits[0][2]}.", results=docs)


# ──────────────────────────────────────────────────────────────────────────
# Helpers (shared shape with the wiki provider)
# ──────────────────────────────────────────────────────────────────────────

_STOP = {
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
    "company",
}


def _extract_terms(question: str) -> list[str]:
    words = re.findall(r"[a-z0-9-]+", question.lower())
    return [w for w in words if w not in _STOP and len(w) > 2]


def _title_of(text: str, path: Path) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()


def _snippet_for(text: str, terms: list[str]) -> str:
    lower = text.lower()
    best_idx, best_score = -1, 0
    for i, para in enumerate(re.split(r"\n\s*\n", text)):
        pl = para.lower()
        score = sum(pl.count(t) for t in terms)
        if score > best_score:
            best_score, best_idx = score, i
    if best_idx >= 0:
        return re.split(r"\n\s*\n", text)[best_idx][:300]
    for t in terms:
        idx = lower.find(t)
        if idx >= 0:
            return text[max(0, idx - 60) : idx + 240]
    return ""
