"""
Brain Context Provider
======================

The graph IS the Brain's living map. ``query_brain`` reads it (recall how the \
company works, find a process, see who owns what); ``update_brain`` synthesizes \
new process knowledge into it and exports the executable skill file.

The only writable provider: collection providers (wiki/slack/drive) return \
``Document`` results, and the orchestrator funnels them through \
``update_brain`` via the skills engine — preserving single-write-surface safety.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from context_brain import graph_schema
from context_brain.providers.base import Answer, ContextProvider, Document, Status
from context_brain.settings import get_settings

log = logging.getLogger(__name__)


class BrainProvider(ContextProvider):
    """Read/write access to the company knowledge graph + skills engine."""

    id = "brain"
    name = "Context Brain (graph + skills)"

    # ── Health ─────────────────────────────────────────────────────────────
    def status(self) -> Status:
        try:
            s = graph_schema.stats()
            return Status(ok=True, detail=f"{s.node_count} nodes, {s.edge_count} edges")
        except Exception as exc:  # pragma: no cover - requires live DB
            return Status(ok=False, detail=f"{type(exc).__name__}: {exc}")

    # ── Read ───────────────────────────────────────────────────────────────
    def query(self, question: str) -> Answer:
        try:
            return self._safe_query(question)
        except Exception as exc:  # pragma: no cover - requires live DB
            log.warning("brain query failed: %s", exc)
            return Answer(text=f"Brain query failed: {type(exc).__name__}: {exc}")

    def _safe_query(self, question: str) -> Answer:
        target = _extract_target(question)
        hops = get_settings().graph_default_hops
        # Neighborhood / "who owns X" / "what connects to X" questions.
        if target and any(
            kw in question.lower()
            for kw in ("connect", "neighbor", "related", "linked", "around", "own", "uses", "govern")
        ):
            sg = graph_schema.subgraph(target, hops=hops)
            if sg["nodes"]:
                return Answer(
                    text=f"{len(sg['nodes'])} nodes within {hops} hops of {target!r} ({len(sg['edges'])} edges):",
                    results=_subgraph_docs(sg),
                )
        # Direct lookup: a named process.
        if target:
            proc = graph_schema.get_process(target)
            if proc:
                return Answer(
                    text=_describe_process(proc),
                    results=[_process_doc(proc)],
                )
            nodes = graph_schema.find_nodes(query=target, limit=20)
            if nodes:
                return Answer(
                    text=f"Found {len(nodes)} node(s) matching {target!r}:",
                    results=[_node_doc(n) for n in nodes],
                )
        # Whole-graph summary.
        s = graph_schema.stats()
        if s.node_count == 0:
            return Answer(
                text="The Brain is empty. Gather knowledge via query_slack/query_drive/query_wiki, then synthesize a process with update_brain."
            )
        breakdown = ", ".join(f"{k}: {v}" for k, v in s.by_label.items())
        return Answer(text=f"Brain has {s.node_count} nodes / {s.edge_count} edges. By label: {breakdown}.")

    # ── Write (synthesis → graph + exported skill) ─────────────────────────
    async def aupdate(self, instruction: str) -> Answer:
        from context_brain.skills_engine import synthesize_from_instruction

        try:
            result = await synthesize_from_instruction(instruction)
            skill_note = f" Exported skill: {result.skill_file}." if result.skill_file else ""
            return Answer(
                text=result.summary + skill_note,
                results=[
                    Document(
                        id=str(i),
                        name=n["value"],
                        snippet=n.get("labels", [""])[0]
                        if isinstance(n.get("labels"), list)
                        else str(n.get("label", "")),
                    )
                    for i, n in enumerate(result.nodes)
                ],
            )
        except Exception as exc:  # pragma: no cover - requires live model + DB
            log.exception("brain update failed")
            return Answer(text=f"Brain update failed: {type(exc).__name__}: {exc}")


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────


def _extract_target(question: str) -> str | None:
    """Pull a likely process/topic identifier out of a question."""
    import re

    q = question.strip().strip("?.").strip()
    m = re.search(r"[\"']([A-Za-z0-9 _./-]{3,})[\"']", q)
    if m:
        return m.group(1).strip()
    # A bare CamelCase / kebab token (common process names like RefundHandling).
    m = re.search(r"\b([A-Z][A-Za-z0-9-]{3,})\b", q)
    if m:
        return m.group(1)
    return None


def _describe_process(proc: dict[str, Any]) -> str:
    """Render a process dict (from get_process) into a readable summary."""
    p = proc["process"]
    steps = proc.get("steps", [])
    lines = [f"Process: {p.get('label') or p.get('value')}"]
    for i, s in enumerate(steps, 1):
        bits = [f"{i}. {s.get('label') or s.get('value')}"]
        if s.get("description"):
            bits.append(f"   {s['description']}")
        if s.get("systems"):
            bits.append(f"   uses: {', '.join(s['systems'])}")
        if s.get("policies"):
            bits.append(f"   governed by: {', '.join(s['policies'])}")
        lines.append("\n".join(bits))
    owners = proc.get("owners", [])
    if owners:
        lines.append("Owners: " + ", ".join(f"{o['kind']}:{o['value']}" for o in owners))
    sources = proc.get("sources", [])
    if sources:
        lines.append("Provenance: " + "; ".join(src.get("value", "") for src in sources))
    return "\n".join(lines)


def _process_doc(proc: dict[str, Any]) -> Document:
    p = proc["process"]
    return Document(
        id=str(p.get("value", "")),
        name=str(p.get("label") or p.get("value", "")),
        snippet=_describe_process(proc)[:500],
        raw={"process": proc},
    )


def _node_doc(node: dict[str, Any]) -> Document:
    return Document(
        id=str(node["id"]),
        name=str(node.get("value", node.get("id"))),
        snippet=f"{node.get('label', 'Entity')}: "
        + json.dumps({k: v for k, v in node.items() if k not in ("id", "value", "label")}, default=str)[:300],
    )


def _subgraph_docs(sg: dict[str, list[dict[str, Any]]]) -> list[Document]:
    return [
        Document(id=str(n["id"]), name=str(n.get("value", n.get("id"))), snippet=n.get("label", "Entity"))
        for n in sg["nodes"]
    ]
