"""Unit tests for the company-knowledge graph vocabulary + helpers (no DB)."""

from __future__ import annotations

import pytest
from context_brain.graph_schema import EDGE_TYPES, NODE_LABELS, canonical_edge, canonical_label


class TestCanonicalLabel:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("process", "Process"),
            ("Process", "Process"),
            ("step", "Step"),
            ("decision", "Decision"),
            ("policy", "Policy"),
            ("role", "Role"),
            ("team", "Team"),
            ("person", "Person"),
            ("system", "System"),
            ("document", "Document"),
            ("doc", "Document"),
            ("tag", "Tag"),
        ],
    )
    def test_aliases(self, raw: str, expected: str) -> None:
        assert canonical_label(raw) == expected

    def test_pascal_passes_through(self) -> None:
        assert canonical_label("Policy") == "Policy"

    def test_unknown_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown node kind"):
            canonical_label("bogus")


class TestCanonicalEdge:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("has_step", "HAS_STEP"),
            ("HAS_STEP", "HAS_STEP"),
            ("next", "NEXT"),
            ("if", "IF"),
            ("governed-by", "GOVERNED_BY"),
            ("owned_by", "OWNED_BY"),
            ("uses", "USES"),
            ("extracted_from", "EXTRACTED_FROM"),
        ],
    )
    def test_aliases(self, raw: str, expected: str) -> None:
        assert canonical_edge(raw) == expected

    def test_unknown_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown edge type"):
            canonical_edge("bogus")


def test_vocabularies_match_company_model() -> None:
    assert "Process" in NODE_LABELS
    assert "Step" in NODE_LABELS
    assert "Decision" in NODE_LABELS
    assert "Policy" in NODE_LABELS
    assert "System" in NODE_LABELS
    assert "HAS_STEP" in EDGE_TYPES
    assert "NEXT" in EDGE_TYPES
    assert "IF" in EDGE_TYPES
    assert "GOVERNED_BY" in EDGE_TYPES
    assert "EXTRACTED_FROM" in EDGE_TYPES
