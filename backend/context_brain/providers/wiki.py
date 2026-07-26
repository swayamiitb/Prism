"""
Wiki Context Provider
=====================

The company wiki — markdown runbooks, policies, and decisions. Reads documented
knowledge; writes new pages as the Brain learns. Filesystem-backed by default
(point ``WIKI_PATH`` at a git repo for durable, audited storage).

This is the direct counterpart to scout's wiki context provider, retargeted
from generic "company knowledge" to the Brain's documented-process layer.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from context_brain.providers.base import Answer, ContextProvider, Document, Status

log = logging.getLogger(__name__)

# Seeded wiki lives in the repo so the Brain runs on real content with no setup.
DEFAULT_WIKI_PATH = Path(__file__).resolve().parents[2] / "data" / "northwind" / "wiki"


def _wiki_root() -> Path:
    import os

    return Path(os.environ.get("WIKI_PATH", str(DEFAULT_WIKI_PATH)))


class WikiProvider(ContextProvider):
    """Read/write the local company wiki."""

    id = "wiki"
    name = "Company Wiki"

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or _wiki_root()

    # ── Health ─────────────────────────────────────────────────────────────
    def status(self) -> Status:
        if not self.root.exists():
            return Status(ok=False, detail=f"wiki path missing: {self.root}")
        pages = list(self.root.rglob("*.md"))
        return Status(ok=True, detail=f"{len(pages)} page(s) at {self.root}")

    # ── Read ───────────────────────────────────────────────────────────────
    def query(self, question: str) -> Answer:
        if not self.root.exists():
            return Answer(text=f"Wiki not found at {self.root}.")
        terms = _extract_terms(question)
        hits: list[tuple[int, Path, str, str]] = []
        for page in self.root.rglob("*.md"):
            try:
                text = page.read_text(encoding="utf-8")
            except OSError:
                continue
            lower = text.lower()
            # Score by term frequency in the page.
            score = sum(lower.count(t) for t in terms)
            # Boost if terms appear in the title/first heading.
            title = _title_of(text, page)
            score += 3 * sum(t in title.lower() for t in terms)
            if score > 0:
                snippet = _snippet_for(text, terms) or text[:200]
                hits.append((score, page, title, snippet))
        if not hits:
            return Answer(text=f"No wiki pages match {question!r}.")
        hits.sort(key=lambda h: h[0], reverse=True)
        docs = [
            Document(
                id=str(p),
                name=title,
                uri=str(p.relative_to(self.root)) if p.is_relative_to(self.root) else str(p),
                source="wiki",
                snippet=snip[:400],
            )
            for _, p, title, snip in hits[:8]
        ]
        return Answer(text=f"{len(hits)} wiki page(s) match. Top: {hits[0][2]}.", results=docs)

    # ── Write ──────────────────────────────────────────────────────────────
    async def aupdate(self, instruction: str) -> Answer:
        """Create a wiki page from a natural-language instruction."""
        title, body = _parse_wiki_instruction(instruction)
        if not title:
            return Answer(text="Couldn't determine a page title from the instruction.")
        slug = _slug(title)
        self.root.mkdir(parents=True, exist_ok=True)
        page = self.root / f"{slug}.md"
        page.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
        return Answer(
            text=f"Saved wiki page {page.relative_to(self.root)} ({len(body)} chars).",
            results=[Document(id=str(page), name=title, uri=str(page), source="wiki")],
        )


# ──────────────────────────────────────────────────────────────────────────
# Helpers
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
    "when",
    "where",
    "why",
    "handle",
    "handled",
    "handles",
    "tell",
    "me",
    "about",
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
    # Scan paragraphs and pick the most term-rich one.
    for i, para in enumerate(re.split(r"\n\s*\n", text)):
        pl = para.lower()
        score = sum(pl.count(t) for t in terms)
        if score > best_score:
            best_score, best_idx = score, i
    if best_idx >= 0:
        return re.split(r"\n\s*\n", text)[best_idx][:300]
    # Fall back to first window containing any term.
    for t in terms:
        idx = lower.find(t)
        if idx >= 0:
            return text[max(0, idx - 60) : idx + 240]
    return ""


def _parse_wiki_instruction(instruction: str) -> tuple[str, str]:
    """Best-effort: pull a title and body out of 'write a wiki page titled X: ...'."""
    m = re.search(r"titled?\s+[\"']?([^\"':\n]+)[\"']?\s*[:\-]?\s*(.*)", instruction, re.S | re.I)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    # Otherwise first line is the title, rest is the body.
    parts = instruction.strip().split("\n", 1)
    title = parts[0].strip().strip(".")
    body = parts[1].strip() if len(parts) > 1 else ""
    return title, body


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "page"
