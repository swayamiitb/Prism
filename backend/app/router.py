"""
Context Brain — API routes
==========================

  GET  /health             liveness probe
  GET  /providers          list providers + status
  GET  /providers/{id}     one provider's status
  POST /providers/{id}/query  debug-query a single provider directly
  POST /chat               one-shot agent invocation (JSON)
  POST /chat/stream        agent invocation as SSE (token stream)
  GET  /graph              the whole knowledge graph (for visualization)
  GET  /graph/stats        aggregate counts
  GET  /graph/subgraph     neighborhood around a node value
  POST /graph/query        raw read-only Cypher
  GET  /processes          list synthesized Processes in the graph
  GET  /processes/{value}  a Process + its steps/decisions/policies/owners/provenance
  GET  /skills             list exported executable skill files
  GET  /skills/{process}   read a skill file as YAML
  POST /skills/{process}/export  re-export a skill from the graph
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

router = APIRouter()
log = logging.getLogger("context_brain.router")


# ──────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    thread_id: str = "default"


class ProviderQueryRequest(BaseModel):
    question: str = Field(..., min_length=1)


class CypherRequest(BaseModel):
    cypher: str = Field(..., min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(1000, ge=1, le=5000)


# ──────────────────────────────────────────────────────────────────────────
# Health
# ──────────────────────────────────────────────────────────────────────────


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ──────────────────────────────────────────────────────────────────────────
# Providers
# ──────────────────────────────────────────────────────────────────────────


@router.get("/providers")
async def list_providers() -> dict[str, Any]:
    from context_brain.contexts import provider_status_rows

    return {"providers": provider_status_rows()}


@router.get("/providers/{provider_id}")
async def provider_status(provider_id: str) -> dict[str, Any]:
    from context_brain.contexts import get_provider

    provider = get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider_id!r}")
    s = provider.status()
    return {
        "id": provider.id,
        "name": provider.name,
        "ok": s.ok,
        "detail": s.detail,
        "writable": provider.is_writable(),
    }


@router.post("/providers/{provider_id}/query")
async def provider_query(provider_id: str, body: ProviderQueryRequest) -> dict[str, Any]:
    from context_brain.contexts import get_provider

    provider = get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail=f"unknown provider {provider_id!r}")
    answer = await provider.aquery(body.question)
    return answer.as_dict()


# ──────────────────────────────────────────────────────────────────────────
# Chat (one-shot + streaming)
# ──────────────────────────────────────────────────────────────────────────


@router.post("/chat")
async def chat(body: ChatRequest) -> dict[str, Any]:
    from context_brain.agent import ainvoke

    try:
        return await ainvoke(body.message, thread_id=body.thread_id)
    except Exception as exc:
        log.exception("agent invocation failed")
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc


@router.post("/chat/stream")
async def chat_stream(body: ChatRequest) -> EventSourceResponse:
    from context_brain.agent import astream

    async def event_generator():
        try:
            async for kind, payload in astream(body.message, thread_id=body.thread_id):
                if kind == "token":
                    yield {"event": "token", "data": json.dumps({"text": payload})}
                elif kind == "tool":
                    yield {"event": "tool", "data": json.dumps({"name": payload})}
                elif kind == "done":
                    yield {"event": "done", "data": json.dumps(payload)}
        except Exception as exc:
            log.exception("agent stream failed")
            yield {"event": "error", "data": json.dumps({"detail": f"{type(exc).__name__}: {exc}"})}

    return EventSourceResponse(event_generator())


# ──────────────────────────────────────────────────────────────────────────
# Graph (visualization + query)
# ──────────────────────────────────────────────────────────────────────────


@router.get("/graph")
async def get_graph(limit: int = 2000) -> dict[str, Any]:
    from context_brain.graph_schema import full_graph

    try:
        return full_graph(limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"graph unavailable: {type(exc).__name__}: {exc}") from exc


@router.get("/graph/stats")
async def get_graph_stats() -> dict[str, Any]:
    from context_brain.graph_schema import stats as graph_stats

    try:
        s = graph_stats()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"graph unavailable: {type(exc).__name__}: {exc}") from exc
    return {
        "node_count": s.node_count,
        "edge_count": s.edge_count,
        "by_label": s.by_label,
        "by_edge": s.by_edge,
    }


@router.get("/graph/subgraph")
async def get_subgraph(value: str, hops: int = 2, limit: int = 500) -> dict[str, Any]:
    from context_brain.graph_schema import subgraph

    try:
        return subgraph(value, hops=hops, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"graph unavailable: {type(exc).__name__}: {exc}") from exc


@router.post("/graph/query")
async def graph_query(body: CypherRequest) -> dict[str, Any]:
    """Run a read-only Cypher query. Write keywords are rejected."""
    forbidden = ("create", "merge", "delete", "detach", "set ", "drop", "remove", "call {")
    lowered = body.cypher.lower()
    if any(f in lowered for f in forbidden):
        raise HTTPException(status_code=400, detail="only read-only MATCH queries are allowed here")
    from context_brain.graph_schema import session

    try:
        with session() as tx:
            records = tx.run(body.cypher, **body.params).data(body.limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{type(exc).__name__}: {exc}") from exc
    return {"records": records}


# ──────────────────────────────────────────────────────────────────────────
# Processes
# ──────────────────────────────────────────────────────────────────────────


@router.get("/processes")
async def list_processes() -> dict[str, Any]:
    from context_brain.graph_schema import session

    try:
        with session() as tx:
            rows = tx.run(
                "MATCH (p:Process) RETURN p.value AS value, p.label AS label, "
                "p.description AS description, p.confidence AS confidence, p.last_seen AS last_seen "
                "ORDER BY p.last_seen DESC"
            ).data()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"graph unavailable: {type(exc).__name__}: {exc}") from exc
    return {"processes": rows}


@router.get("/processes/{value}")
async def get_process(value: str) -> dict[str, Any]:
    from context_brain.graph_schema import get_process as fetch

    try:
        proc = fetch(value)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"graph unavailable: {type(exc).__name__}: {exc}") from exc
    if proc is None:
        raise HTTPException(status_code=404, detail=f"no Process named {value!r}")
    return proc


# ──────────────────────────────────────────────────────────────────────────
# Skills (the executable skills files)
# ──────────────────────────────────────────────────────────────────────────


@router.get("/skills")
async def list_skills() -> dict[str, Any]:
    from context_brain.skills_engine import list_exported_skills

    return {"skills": list_exported_skills()}


@router.get("/skills/{process}")
async def read_skill(process: str) -> dict[str, str]:
    from context_brain.settings import get_settings

    out_dir = Path(get_settings().skills_export_dir)
    slug = "".join(c if c.isalnum() else "-" for c in process.lower()).strip("-")
    candidates = [out_dir / f"{slug}.skill.yml", out_dir / f"{process}.skill.yml"]
    for c in candidates:
        if c.exists():
            return {"process": process, "yaml": c.read_text(encoding="utf-8")}
    raise HTTPException(status_code=404, detail=f"no exported skill for {process!r}")


@router.post("/skills/{process}/export")
async def export_skill_route(process: str) -> dict[str, Any]:
    from context_brain.skills_engine import export_skill

    path = export_skill(process)
    if path is None:
        raise HTTPException(status_code=404, detail=f"no Process named {process!r} to export")
    return {"process": process, "file": path}
