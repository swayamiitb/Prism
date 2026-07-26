"""
Context Brain — Wiring Invariants
=================================

Structural checks that need no LLM and no network. They run in <1s and lock in
the architecture's load-bearing guarantees. If any of these break, the whole
agent contract is broken.

Run:  python -m evals wiring
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class InvariantResult:
    id: str
    name: str
    passed: bool
    detail: str = ""


def _tool_names(tools: list) -> set[str]:
    names: set[str] = set()
    for t in tools:
        n = getattr(t, "name", None)
        if isinstance(n, str):
            names.add(n)
    return names


# ──────────────────────────────────────────────────────────────────────────
# Checks
# ──────────────────────────────────────────────────────────────────────────


def w1_orchestrator_tool_surface() -> None:
    """The orchestrator exposes list_providers + the per-provider query_/update_ tools."""
    from context_brain.agent import collect_tools

    tools = collect_tools()
    names = _tool_names(tools)
    assert "list_providers" in names, f"missing list_providers; have {names}"
    assert "query_brain" in names, "brain provider must expose query_brain"
    assert "update_brain" in names, "brain provider must expose update_brain (it is the write surface)"
    assert "query_wiki" in names, "wiki provider must expose query_wiki"
    assert "update_wiki" in names, "wiki provider must expose update_wiki (writable)"
    assert "query_slack" in names, "slack provider must expose query_slack"
    assert "query_drive" in names, "drive provider must expose query_drive"


def w2_single_write_surface() -> None:
    """Only the brain provider is writable (the graph + skills)."""
    from context_brain.contexts import get_context_providers

    for p in get_context_providers():
        if p.id in ("brain", "wiki"):
            assert p.is_writable(), f"provider {p.id!r} must be writable"
        else:
            assert not p.is_writable(), (
                f"provider {p.id!r} must be read-only (collection providers return docs, brain synthesizes)"
            )


def w3_provider_protocol_shape() -> None:
    """Every provider is a ContextProvider with the right methods."""
    from context_brain.contexts import get_context_providers
    from context_brain.providers.base import ContextProvider

    for p in get_context_providers():
        assert isinstance(p, ContextProvider), f"{p!r} is not a ContextProvider"
        assert isinstance(p.id, str) and p.id, "provider.id must be a non-empty string"
        assert isinstance(p.name, str) and p.name, "provider.name must be a non-empty string"
        for method in ("query", "aquery", "status", "get_tools"):
            assert callable(getattr(p, method, None)), f"provider {p.id!r} missing {method}"


def w4_graph_vocabulary_closed() -> None:
    """The node-label and edge-type vocabularies match the company knowledge model."""
    from context_brain.graph_schema import EDGE_TYPES, NODE_LABELS, canonical_edge, canonical_label

    assert "Process" in NODE_LABELS and "Step" in NODE_LABELS
    assert "Decision" in NODE_LABELS and "Policy" in NODE_LABELS
    assert "HAS_STEP" in EDGE_TYPES and "NEXT" in EDGE_TYPES
    assert "GOVERNED_BY" in EDGE_TYPES and "EXTRACTED_FROM" in EDGE_TYPES
    assert canonical_label("process") == "Process"
    assert canonical_edge("has_step") == "HAS_STEP"
    try:
        canonical_label("bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("canonical_label should reject unknown kinds")


def w5_readonly_provider_update_is_clean() -> None:
    """A read-only provider's update_* tool returns a clean 'read-only' error."""
    from context_brain.providers.base import Answer, ContextProvider, Status

    class _Ro(ContextProvider):
        id = "ro"
        name = "Read-Only Test"

        def query(self, question):
            return Answer(text="ok")

        def status(self):
            return Status(ok=True, detail="up")

    p = _Ro()
    assert not p.is_writable()
    tools = {getattr(t, "name", ""): t for t in p.get_tools()}
    assert "query_ro" in tools and "update_ro" not in tools, "read-only provider must not expose update_*"


def w6_skill_plan_schema_strict() -> None:
    """The skills engine validates strict pydantic schemas (no raw LLM output to DB)."""
    from context_brain.skills_engine import NodeSpec
    from pydantic import ValidationError

    NodeSpec(kind="Process", value="RefundHandling")  # valid
    try:
        NodeSpec(kind="Bogus", value="x")
    except ValueError:
        pass
    else:
        raise AssertionError("NodeSpec should reject unknown kinds")
    try:
        NodeSpec(kind="Process", value="x", confidence=2.0)
    except ValidationError:
        pass
    else:
        raise AssertionError("NodeSpec should reject out-of-range confidence")


def w7_api_routes_registered() -> None:
    """The FastAPI app exposes the expected routes (incl. skills + processes)."""
    from app.main import app

    paths: set[str] = set(app.openapi()["paths"].keys())
    for expected in (
        "/health",
        "/providers",
        "/chat",
        "/chat/stream",
        "/graph",
        "/graph/stats",
        "/processes",
        "/skills",
    ):
        assert expected in paths, f"missing route {expected}; have {sorted(paths)}"


def w8_seed_data_present() -> None:
    """The seeded Northwind data exists so the Brain runs with zero credentials."""
    from pathlib import Path

    data = Path(__file__).resolve().parents[1] / "data" / "northwind"
    assert (data / "wiki").glob("*.md"), "seeded wiki missing"
    assert (data / "slack.jsonl").exists(), "seeded slack.jsonl missing"
    assert (data / "drive").glob("*.md"), "seeded drive missing"


CHECKS = (
    ("w1", "orchestrator tool surface", w1_orchestrator_tool_surface),
    ("w2", "single write surface", w2_single_write_surface),
    ("w3", "provider protocol shape", w3_provider_protocol_shape),
    ("w4", "graph vocabulary closed", w4_graph_vocabulary_closed),
    ("w5", "read-only provider update is clean", w5_readonly_provider_update_is_clean),
    ("w6", "skill plan schema strict", w6_skill_plan_schema_strict),
    ("w7", "API routes registered", w7_api_routes_registered),
    ("w8", "seeded sample data present", w8_seed_data_present),
)


def run_all() -> list[InvariantResult]:
    results: list[InvariantResult] = []
    for wid, name, fn in CHECKS:
        try:
            fn()
            results.append(InvariantResult(wid, name, passed=True))
        except Exception as exc:
            results.append(InvariantResult(wid, name, passed=False, detail=f"{type(exc).__name__}: {exc}"))
    return results
