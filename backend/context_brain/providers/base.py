"""
SAAS AI Context Providers — base contract
=========================================

This is the open-source port of scout's ``ContextProvider`` abstraction.
Each external data source (the graph itself, the web, DNS, GitHub, …) is a
``ContextProvider``: a sub-agent that exposes a ``query_<id>`` tool to read
data and, optionally, an ``update_<id>`` tool to write data.

The orchestrator agent sees one clean tool per provider, so the messy details
of each source's API quirks never pollute the main context — exactly scout's
"isolation by sub-agent" principle.

Design rules (inherited from scout):
  * Providers self-report ``status()`` — ``ok`` plus a human detail string.
  * Read-only providers leave ``aupdate`` as the base no-op; the generated
    ``update_<id>`` tool then returns a clean "read-only" error instead of
    silently failing.
  * ``get_tools()`` builds the LangChain ``StructuredTool``s from the methods,
    so registering a provider is enough to expose its tools to the agent.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Shared result types
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class Status:
    """Provider health: ``ok`` plus a short human-readable detail."""

    ok: bool
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "detail": self.detail}


@dataclass
class Document:
    """A single finding a provider returns from a collection/search."""

    id: str
    name: str
    uri: str = ""
    source: str = ""
    snippet: str = ""
    # Structured entities that the graph provider can ingest directly.
    entities: list[dict[str, Any]] = field(default_factory=list)
    # Raw payload for the orchestrator to read if it wants detail.
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Answer:
    """A provider's response to a ``query``."""

    text: str
    results: list[Document] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"text": self.text, "results": [r.__dict__ for r in self.results]}


# ──────────────────────────────────────────────────────────────────────────
# Pydantic schemas for the auto-generated tools (so the LLM sees clean args)
# ──────────────────────────────────────────────────────────────────────────


class QueryArgs(BaseModel):
    """Arguments for a provider's ``query_<id>`` tool."""

    question: str = Field(..., description="A natural-language question or target to investigate.")


class UpdateArgs(BaseModel):
    """Arguments for a provider's ``update_<id>`` tool (writable providers only)."""

    instruction: str = Field(..., description="A natural-language instruction on what to create or change.")


# ──────────────────────────────────────────────────────────────────────────
# The base class
# ──────────────────────────────────────────────────────────────────────────


class ContextProvider:
    """Base contract every provider implements.

    Subclasses set ``id`` and ``name``, implement ``query``/``status``, and
    optionally override ``aupdate`` to become writable. ``get_tools()`` then
    emits the matching ``query_<id>`` (+ ``update_<id>``) LangChain tools.
    """

    id: str = "base"
    name: str = "Base Provider"

    # ── Read ───────────────────────────────────────────────────────────────
    def query(self, question: str) -> Answer:  # pragma: no cover - interface
        raise NotImplementedError

    async def aquery(self, question: str) -> Answer:
        """Async query. Default delegates to the sync ``query``."""
        return self.query(question)

    # ── Write (optional) ───────────────────────────────────────────────────
    async def aupdate(self, instruction: str) -> Answer:
        """Writable providers override this. Base = read-only."""
        return Answer(
            text=(
                f"The '{self.id}' provider is read-only; it cannot process updates. "
                "To change data, route the write through a writable provider."
            )
        )

    def is_writable(self) -> bool:
        """True when the subclass actually overrides ``aupdate``."""
        return type(self).aupdate is not ContextProvider.aupdate

    # ── Health ─────────────────────────────────────────────────────────────
    def status(self) -> Status:  # pragma: no cover - interface
        raise NotImplementedError

    # ── Tool generation ────────────────────────────────────────────────────
    def get_tools(self) -> list[StructuredTool]:
        """Build the LangChain tools this provider exposes to the orchestrator.

        Always emits ``query_<id>``. Emits ``update_<id>`` only if the
        provider overrides ``aupdate`` (i.e. it is genuinely writable).
        """
        query_name = f"query_{self.id}"
        update_name = f"update_{self.id}"
        tools: list[StructuredTool] = [
            StructuredTool.from_function(
                self._query_tool,
                name=query_name,
                description=self._query_description(),
                args_schema=QueryArgs,
                coroutine=self._aquery_tool,
            )
        ]
        if self.is_writable():
            tools.append(
                StructuredTool.from_function(
                    self._update_tool,
                    name=update_name,
                    description=self._update_description(),
                    args_schema=UpdateArgs,
                    coroutine=self._aupdate_tool,
                )
            )
        return tools

    # ── Tool wrappers (sync + async, both routed through the provider) ─────
    def _query_tool(self, question: str) -> str:
        answer = self.query(question)
        return _format_answer(answer)

    async def _aquery_tool(self, question: str) -> str:
        answer = await self.aquery(question)
        return _format_answer(answer)

    def _update_tool(self, instruction: str) -> str:
        # Sync wrapper for writable providers; most writers are async-only.
        import asyncio

        answer = asyncio.run(self.aupdate(instruction))
        return _format_answer(answer)

    async def _aupdate_tool(self, instruction: str) -> str:
        answer = await self.aupdate(instruction)
        return _format_answer(answer)

    # ── Descriptions (subclasses may override for richer tool docs) ────────
    def _query_description(self) -> str:
        return (
            f"Query the {self.name} ({self.id}) context for information. "
            "Pass a natural-language question or an investigation target "
            "(e.g. a domain, a GitHub handle, a search topic)."
        )

    def _update_description(self) -> str:
        return (
            f"Write to the {self.name} ({self.id}) context. "
            "Pass a natural-language instruction describing what to create or change."
        )


def _format_answer(answer: Answer) -> str:
    """Render an ``Answer`` as the string the LLM sees in tool output."""
    lines: list[str] = []
    if answer.text:
        lines.append(answer.text)
    for i, doc in enumerate(answer.results, 1):
        lines.append(f"\n[{i}] {doc.name}")
        if doc.uri:
            lines.append(f"    uri: {doc.uri}")
        if doc.snippet:
            lines.append(f"    {doc.snippet}")
    return "\n".join(lines) if lines else "(no results)"


# Type alias for the registry factory.
ProviderFactory = Callable[[], "ContextProvider | None"]
AsyncProviderFactory = Callable[[], Awaitable["ContextProvider | None"]]
