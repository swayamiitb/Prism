"""
Context Brain — Skills Engine
=============================

The differentiator. The Brain doesn't just store documents — it synthesizes \
process knowledge into an executable skills layer:

  1. A natural-language "how we handle X" description → a validated plan of \
     Process/Step/Decision/Policy/Role/System operations → applied to the graph.
  2. The same process → an exported ``.skill.yml`` file an external AI agent \
     can load and execute (trigger, owner, steps/decisions, constraints, systems).

This is the literal "executable skills file" from the Context Brain essay.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from context_brain import graph_schema
from context_brain.instructions import CONTEXT_BRAIN_WRITE
from context_brain.settings import default_model, get_settings
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, ValidationError, field_validator

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# The synthesis plan schema (what the LLM must emit to build the graph)
# ──────────────────────────────────────────────────────────────────────────


class NodeSpec(BaseModel):
    """One node to upsert."""

    kind: str = Field(
        ...,
        description="Canonical node label: Process, Step, Decision, Policy, Role, Team, Person, System, Document, Tag.",
    )
    value: str = Field(
        ..., description="Canonical identifier, e.g. 'RefundHandling', 'VerifyCharge', 'MaxRefund2xPolicy'."
    )
    label: str | None = None
    description: str = ""
    confidence: float = Field(0.8, ge=0.0, le=1.0)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("kind")
    @classmethod
    def _canonical_kind(cls, v: str) -> str:
        return graph_schema.canonical_label(v)


class EdgeSpec(BaseModel):
    """One edge to upsert (endpoints referenced by node ``value``)."""

    from_value: str = Field(..., alias="from", description="value of the source node")
    to_value: str = Field(..., alias="to", description="value of the target node")
    type: str = Field(
        ...,
        description="Canonical edge type: HAS_STEP, NEXT, IF, GOVERNED_BY, OWNED_BY, EXECUTED_BY, USES, EXTRACTED_FROM.",
    )
    confidence: float = Field(0.7, ge=0.0, le=1.0)
    properties: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def _canonical_type(cls, v: str) -> str:
        return graph_schema.canonical_edge(v)


class SkillPlan(BaseModel):
    """A validated plan of node + edge operations + skill metadata."""

    process_value: str = Field(..., description="The canonical Process value this skill is about.")
    name: str = Field(..., description="Human-readable skill name.")
    trigger: str = Field("", description="When this skill runs, e.g. 'customer requests a refund'.")
    owner: str = Field("", description="Owning role/team, e.g. 'role:support-agent'.")
    nodes: list[NodeSpec] = Field(default_factory=list)
    edges: list[EdgeSpec] = Field(default_factory=list)
    constraints: list[str] = Field(
        default_factory=list, description="Hard rules, e.g. 'never refund more than 2x original'."
    )
    summary: str = ""


@dataclass
class SynthesisResult:
    summary: str
    process_value: str
    nodes_filed: int
    edges_filed: int
    skill_file: str | None  # path to exported .skill.yml, if exported
    nodes: list[dict[str, Any]] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────
# LLM plan extraction
# ──────────────────────────────────────────────────────────────────────────

_PLANNER_SYSTEM = (
    CONTEXT_BRAIN_WRITE + "\n\nEmit your synthesis as STRICT JSON only — no prose, no code fences. "
    'Schema: {"process_value": str, "name": str, "trigger": str, "owner": str, '
    '"nodes": [{"kind": str, "value": str, "label": str|null, "description": str, '
    '"confidence": float, "properties": {}}, ...], "edges": [{"from": str, "to": str, '
    '"type": str, "confidence": float, "properties": {}}, ...], "constraints": [str, ...], '
    '"summary": str}. Use only canonical kinds and edge types. Every Process must link its '
    "Steps via HAS_STEP; order Steps with NEXT; model branches with IF (condition in properties.condition). "
    "Link provenance via EXTRACTED_FROM to Document nodes."
)


def _extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of model output (tolerates code fences + preamble)."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        text = match.group(0)
    return json.loads(text)


async def _plan(instruction: str) -> SkillPlan:
    """Ask the local model to produce a validated synthesis plan."""
    model = default_model()
    response = await model.ainvoke([SystemMessage(content=_PLANNER_SYSTEM), HumanMessage(content=instruction)])
    raw = response.content if isinstance(response.content, str) else str(response.content)
    try:
        data = _extract_json(raw)
        return SkillPlan.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        log.warning("skill plan parse failed (%s); raw: %s", exc, raw[:500])
        return SkillPlan(
            process_value="unknown",
            name="unknown",
            summary=f"Could not parse a synthesis plan: {exc}",
        )


# ──────────────────────────────────────────────────────────────────────────
# Apply a plan to the graph
# ──────────────────────────────────────────────────────────────────────────


def _apply(plan: SkillPlan, source: str = "agent") -> tuple[int, int, list[dict[str, Any]]]:
    """Apply a validated plan to the graph. Returns (nodes_filed, edges_filed, nodes)."""
    filed_nodes: list[dict[str, Any]] = []
    for n in plan.nodes:
        try:
            filed_nodes.append(
                graph_schema.upsert_node(
                    n.kind,
                    n.value,
                    label=n.label,
                    description=n.description,
                    source=source,
                    confidence=n.confidence,
                    properties=n.properties,
                )
            )
        except ValueError as exc:
            log.warning("skipping bad node spec %r: %s", n.kind, exc)

    edges_applied = 0
    for e in plan.edges:
        try:
            if graph_schema.upsert_edge(
                e.from_value,
                e.type,
                e.to_value,
                source=source,
                confidence=e.confidence,
                properties=e.properties,
            ):
                edges_applied += 1
        except ValueError as exc:
            log.warning("skipping bad edge spec %r: %s", e.type, exc)

    return len(filed_nodes), edges_applied, filed_nodes


# ──────────────────────────────────────────────────────────────────────────
# Export a process to an executable .skill.yml
# ──────────────────────────────────────────────────────────────────────────


def export_skill(process_value: str, plan: SkillPlan | None = None) -> str | None:
    """Export a process (from the graph, or from a fresh plan) to a .skill.yml file.

    Returns the file path, or None if the process can't be found.
    """
    proc = graph_schema.get_process(process_value)
    if not proc:
        log.warning("export_skill: process %r not in graph", process_value)
        return None

    # Prefer graph-derived structure; fall back to plan metadata.
    process = proc["process"]
    steps_out = []
    for s in proc["steps"]:
        step: dict[str, Any] = {
            "id": s.get("value", ""),
            "name": s.get("label") or s.get("value", ""),
            "description": s.get("description", ""),
        }
        if s.get("systems"):
            step["uses"] = s["systems"]
        if s.get("policies"):
            step["governed_by"] = s["policies"]
        # Decision branch conditions live in NEXT/IF edge properties; surface if present.
        if "condition" in s:
            step["if"] = s["condition"]
        steps_out.append(step)

    skill = {
        "name": plan.name if plan and plan.name else process.get("label") or process_value,
        "process": process_value,
        "trigger": plan.trigger if plan and plan.trigger else process.get("trigger", ""),
        "owner": plan.owner if plan and plan.owner else _first_owner(proc.get("owners", [])),
        "steps": steps_out,
        "constraints": plan.constraints if plan and plan.constraints else [],
        "provenance": [f"{src.get('kind', 'document')}: {src.get('value', '')}" for src in proc.get("sources", [])],
        "meta": {
            "confidence": process.get("confidence", 0.8),
            "source": process.get("source", ""),
            "first_seen": process.get("first_seen", ""),
            "last_seen": process.get("last_seen", ""),
        },
    }

    out_dir = Path(get_settings().skills_export_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = _slug(process_value)
    out_path = out_dir / f"{slug}.skill.yml"
    out_path.write_text(yaml.safe_dump(skill, sort_keys=False, allow_unicode=True), encoding="utf-8")
    log.info("exported skill: %s", out_path)
    return str(out_path)


def _first_owner(owners: list[dict[str, Any]]) -> str:
    if not owners:
        return ""
    o = owners[0]
    return f"{o.get('kind', 'role').lower()}:{o.get('value', '')}"


def _slug(value: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in value.lower()).strip("-") or "skill"


# ──────────────────────────────────────────────────────────────────────────
# End-to-end: instruction → plan → graph → exported skill file
# ──────────────────────────────────────────────────────────────────────────


async def synthesize_from_instruction(instruction: str, source: str = "agent") -> SynthesisResult:
    """The Brain provider calls this: synthesize a process + export its skill file."""
    plan = await _plan(instruction)
    nodes_filed, edges_filed, nodes = _apply(plan, source=source)

    skill_file = None
    if plan.process_value and plan.process_value != "unknown":
        skill_file = export_skill(plan.process_value, plan=plan)

    summary = plan.summary or f"Synthesized {plan.name}: {nodes_filed} nodes, {edges_filed} edges."
    return SynthesisResult(
        summary=summary,
        process_value=plan.process_value,
        nodes_filed=nodes_filed,
        edges_filed=edges_filed,
        skill_file=skill_file,
        nodes=nodes,
    )


def list_exported_skills() -> list[dict[str, Any]]:
    """List all exported .skill.yml files with a light parse of their metadata."""
    out_dir = Path(get_settings().skills_export_dir)
    if not out_dir.exists():
        return []
    out = []
    for p in sorted(out_dir.glob("*.skill.yml")):
        try:
            data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            out.append(
                {
                    "file": str(p),
                    "name": data.get("name", p.stem),
                    "process": data.get("process", ""),
                    "trigger": data.get("trigger", ""),
                    "owner": data.get("owner", ""),
                    "steps": len(data.get("steps", [])),
                }
            )
        except yaml.YAMLError:
            out.append({"file": str(p), "name": p.stem, "process": "", "error": "parse failed"})
    return out
