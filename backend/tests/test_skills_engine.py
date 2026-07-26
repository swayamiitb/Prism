"""Unit tests for skills_engine plan validation + JSON extraction (no LLM/DB)."""

from __future__ import annotations

import json

import pytest
from context_brain.skills_engine import EdgeSpec, NodeSpec, SkillPlan, _extract_json
from pydantic import ValidationError


class TestNodeSpec:
    def test_valid_minimal(self) -> None:
        n = NodeSpec(kind="Process", value="RefundHandling")
        assert n.kind == "Process"
        assert n.confidence == 0.8

    def test_unknown_kind_rejected(self) -> None:
        with pytest.raises(ValueError):
            NodeSpec(kind="Bogus", value="x")

    def test_confidence_range(self) -> None:
        NodeSpec(kind="Step", value="Verify", confidence=0.0)
        NodeSpec(kind="Step", value="Verify", confidence=1.0)
        with pytest.raises(ValidationError):
            NodeSpec(kind="Step", value="Verify", confidence=1.5)
        with pytest.raises(ValidationError):
            NodeSpec(kind="Step", value="Verify", confidence=-0.1)


class TestEdgeSpec:
    def test_alias_from_to(self) -> None:
        e = EdgeSpec.model_validate({"from": "Verify", "to": "Decide", "type": "NEXT"})
        assert e.from_value == "Verify"
        assert e.to_value == "Decide"

    def test_unknown_type_rejected(self) -> None:
        with pytest.raises(ValueError):
            EdgeSpec.model_validate({"from": "a", "to": "b", "type": "BOGUS"})


class TestSkillPlan:
    def test_empty_plan_ok(self) -> None:
        p = SkillPlan(process_value="x", name="x")
        assert p.nodes == [] and p.edges == []

    def test_full_plan(self) -> None:
        p = SkillPlan.model_validate(
            {
                "process_value": "RefundHandling",
                "name": "Refund Handling",
                "trigger": "customer requests refund",
                "owner": "role:support-agent",
                "nodes": [{"kind": "Process", "value": "RefundHandling"}],
                "edges": [{"from": "Verify", "to": "Decide", "type": "NEXT"}],
                "constraints": ["never refund more than 2x original"],
                "summary": "filed",
            }
        )
        assert len(p.nodes) == 1
        assert len(p.edges) == 1
        assert p.summary == "filed"
        assert p.constraints == ["never refund more than 2x original"]


class TestExtractJson:
    def test_plain_json(self) -> None:
        text = json.dumps({"nodes": [], "edges": []})
        assert _extract_json(text) == {"nodes": [], "edges": []}

    def test_fenced_json(self) -> None:
        text = '```json\n{"nodes": [], "summary": "ok"}\n```'
        assert _extract_json(text)["summary"] == "ok"

    def test_json_with_preamble(self) -> None:
        text = 'Here is the plan:\n{"nodes": [{"kind": "Process", "value": "x"}], "edges": []}'
        result = _extract_json(text)
        assert result["nodes"][0]["value"] == "x"

    def test_invalid_raises(self) -> None:
        with pytest.raises(json.JSONDecodeError):
            _extract_json("not json at all")
