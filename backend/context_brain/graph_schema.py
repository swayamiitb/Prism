"""
Context Brain — Graph Schema
============================

The knowledge graph is the Brain's *living map of how the company works*. Every
process, decision, policy, role, and system is a node; every relationship
between them (a process HAS_STEP, a decision branches IF a condition, a process
is GOVERNED_BY a policy) is an edge. Provenance is first-class — every node
traces back to the Slack thread / doc / policy it was derived from.

We talk to Neo4j directly via the ``neo4j`` driver; Cypher is the source of
truth. The single-write-surface principle is preserved: only the Brain provider
(``update_brain``) mutates the graph, through the validated skills engine.

Node labels: Process, Step, Decision, Policy, Role, Team, Person, System,
             Document, Tag.
Edge types:  HAS_STEP, NEXT, IF, GOVERNED_BY, OWNED_BY, EXECUTED_BY, USES,
             EXTRACTED_FROM, MENTIONED_IN.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from context_brain.settings import get_settings
from neo4j import Driver, GraphDatabase

log = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────
# Vocabulary — the company knowledge model
# ──────────────────────────────────────────────────────────────────────────

NODE_LABELS: tuple[str, ...] = (
    "Process",
    "Step",
    "Decision",
    "Policy",
    "Role",
    "Team",
    "Person",
    "System",
    "Document",
    "Tag",
)

EDGE_TYPES: tuple[str, ...] = (
    "HAS_STEP",
    "NEXT",
    "IF",
    "GOVERNED_BY",
    "OWNED_BY",
    "EXECUTED_BY",
    "USES",
    "EXTRACTED_FROM",
    "MENTIONED_IN",
)

_LABEL_ALIASES: dict[str, str] = {
    "process": "Process",
    "step": "Step",
    "decision": "Decision",
    "policy": "Policy",
    "role": "Role",
    "team": "Team",
    "person": "Person",
    "system": "System",
    "document": "Document",
    "doc": "Document",
    "tag": "Tag",
}


def canonical_label(kind: str) -> str:
    """Normalise a kind/label string to a canonical node label.

    Raises ``ValueError`` for unknown kinds so we never silently write a
    typo'd label into the graph (which would create an invisible node).
    """
    key = kind.strip().lower()
    if key in _LABEL_ALIASES:
        return _LABEL_ALIASES[key]
    pascal = key.title().replace("_", "")
    if pascal in NODE_LABELS:
        return pascal
    raise ValueError(f"Unknown node kind {kind!r}. Known: {', '.join(NODE_LABELS)}")


def canonical_edge(kind: str) -> str:
    """Normalise a relationship type to upper-snake CANONICAL form."""
    key = kind.strip().upper().replace(" ", "_").replace("-", "_")
    if key in EDGE_TYPES:
        return key
    raise ValueError(f"Unknown edge type {kind!r}. Known: {', '.join(EDGE_TYPES)}")


# ──────────────────────────────────────────────────────────────────────────
# Driver (lazy singleton)
# ──────────────────────────────────────────────────────────────────────────

_driver: Driver | None = None


def get_driver() -> Driver:
    """Return a process-wide Neo4j driver (created on first use)."""
    global _driver
    if _driver is None:
        s = get_settings()
        _driver = GraphDatabase.driver(s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password))
        log.info("Neo4j driver created for %s", s.neo4j_uri)
    return _driver


def close_driver() -> None:
    """Close the driver — call on app shutdown."""
    global _driver
    if _driver is not None:
        _driver.close()
        _driver = None


@contextmanager
def session() -> Iterator[Any]:
    """Context-managed Neo4j session."""
    yield get_driver().session()


# ──────────────────────────────────────────────────────────────────────────
# Constraints + indexes (idempotent — safe at startup)
# ──────────────────────────────────────────────────────────────────────────

_CONSTRAINTS: dict[str, str] = {
    "Process": "CREATE CONSTRAINT process_value IF NOT EXISTS FOR (n:Process) REQUIRE n.value IS UNIQUE",
    "Step": "CREATE CONSTRAINT step_value IF NOT EXISTS FOR (n:Step) REQUIRE n.value IS UNIQUE",
    "Decision": "CREATE CONSTRAINT decision_value IF NOT EXISTS FOR (n:Decision) REQUIRE n.value IS UNIQUE",
    "Policy": "CREATE CONSTRAINT policy_value IF NOT EXISTS FOR (n:Policy) REQUIRE n.value IS UNIQUE",
    "Role": "CREATE CONSTRAINT role_value IF NOT EXISTS FOR (n:Role) REQUIRE n.value IS UNIQUE",
    "Team": "CREATE CONSTRAINT team_value IF NOT EXISTS FOR (n:Team) REQUIRE n.value IS UNIQUE",
    "Person": "CREATE CONSTRAINT person_value IF NOT EXISTS FOR (n:Person) REQUIRE n.value IS UNIQUE",
    "System": "CREATE CONSTRAINT system_value IF NOT EXISTS FOR (n:System) REQUIRE n.value IS UNIQUE",
    "Document": "CREATE CONSTRAINT document_value IF NOT EXISTS FOR (n:Document) REQUIRE n.value IS UNIQUE",
    "Tag": "CREATE CONSTRAINT tag_value IF NOT EXISTS FOR (n:Tag) REQUIRE n.value IS UNIQUE",
}

_INDEXES: tuple[str, ...] = (
    "CREATE INDEX label_index IF NOT EXISTS FOR (n:_Entity) ON (n.label)",
    "CREATE INDEX first_seen_index IF NOT EXISTS FOR (n:_Entity) ON (n.first_seen)",
    "CREATE INDEX kind_index IF NOT EXISTS FOR (n:_Entity) ON (n.kind)",
)


def ensure_schema() -> None:
    """Create constraints + indexes. Idempotent; call once at startup."""
    with session() as tx:
        for cypher in (*_CONSTRAINTS.values(), *_INDEXES):
            tx.run(cypher)
    log.info("graph schema ensured (%d constraints, %d indexes)", len(_CONSTRAINTS), len(_INDEXES))


# ──────────────────────────────────────────────────────────────────────────
# Write API (the single write surface — used by the Brain provider)
# ──────────────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def upsert_node(
    kind: str,
    value: str,
    *,
    label: str | None = None,
    description: str = "",
    source: str = "",
    confidence: float = 0.8,
    properties: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert-or-merge a node. Returns the node as a plain dict.

    Re-merging a node updates its ``description``/``properties`` and bumps
    ``last_seen`` without duplicating. ``first_seen`` is preserved.
    """
    node_label = canonical_label(kind)
    props = dict(properties or {})
    if description:
        props["description"] = description
    if label:
        props["label"] = label
    props["value"] = value
    props["kind"] = node_label
    props.setdefault("source", source)
    props.setdefault("confidence", confidence)
    props["last_seen"] = _now_iso()

    cypher = (
        f"MERGE (n:{node_label}:_Entity {{value: $value}}) "
        "ON CREATE SET n.first_seen = $now, n.created_by = $source "
        "SET n += $props "
        "RETURN n, labels(n) AS labels"
    )
    with session() as tx:
        rec = tx.run(cypher, value=value, now=_now_iso(), source=source, props=props).single()
    if rec is None:
        return {"label": node_label, "value": value}
    node = rec["n"]
    return {
        "id": node.element_id,
        "labels": rec["labels"],
        "value": node["value"],
        "properties": dict(node),
    }


def upsert_edge(
    src_value: str,
    edge_type: str,
    dst_value: str,
    *,
    source: str = "",
    confidence: float = 0.7,
    properties: dict[str, Any] | None = None,
) -> bool:
    """MERGE a relationship between two nodes matched by ``value``.

    Both endpoints must already exist. Returns ``True`` if created/updated.
    """
    rel = canonical_edge(edge_type)
    props = dict(properties or {})
    props.setdefault("source", source)
    props.setdefault("confidence", confidence)
    props["last_seen"] = _now_iso()

    cypher = (
        "MATCH (a {value: $src}), (b {value: $dst}) "
        f"MERGE (a)-[r:{rel}]->(b) "
        "ON CREATE SET r.first_seen = $now "
        "SET r += $props "
        "RETURN count(r) AS c"
    )
    with session() as tx:
        rec = tx.run(cypher, src=src_value, dst=dst_value, now=_now_iso(), props=props).single()
    return bool(rec and rec["c"] > 0)


# ──────────────────────────────────────────────────────────────────────────
# Read API
# ──────────────────────────────────────────────────────────────────────────


@dataclass
class GraphStats:
    node_count: int
    edge_count: int
    by_label: dict[str, int]
    by_edge: dict[str, int]


def stats() -> GraphStats:
    """Return aggregate counts for the whole graph."""
    with session() as tx:
        nodes = tx.run("MATCH (n:_Entity) RETURN count(n) AS c").single()["c"]
        edges = tx.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        by_label = {
            r["label"]: r["c"]
            for r in tx.run(
                "MATCH (n:_Entity) UNWIND labels(n) AS label "
                "WITH label WHERE label <> '_Entity' "
                "RETURN label, count(*) AS c ORDER BY c DESC"
            )
        }
        by_edge = {
            r["type"]: r["c"] for r in tx.run("MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS c ORDER BY c DESC")
        }
    return GraphStats(nodes, edges, by_label, by_edge)


def full_graph(limit: int = 2000) -> dict[str, list[dict[str, Any]]]:
    """Return the whole graph (capped) for visualization."""
    with session() as tx:
        node_records = tx.run(
            "MATCH (n:_Entity) WITH n ORDER BY n.last_seen DESC LIMIT $limit "
            "RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props",
            limit=limit,
        ).value()
        ids = [r["id"] for r in node_records]
        if not ids:
            return {"nodes": [], "edges": []}
        edge_records = tx.run(
            "MATCH (a)-[r]->(b) WHERE id(a) IN $ids AND id(b) IN $ids "
            "RETURN id(a) AS source, id(b) AS target, type(r) AS type, properties(r) AS props",
            ids=ids,
        ).value()

    nodes = []
    for rec in node_records:
        labels = [lb for lb in rec["labels"] if lb != "_Entity"]
        nodes.append(
            {
                "id": rec["id"],
                "label": labels[0] if labels else "Entity",
                "value": rec["props"].get("value", str(rec["id"])),
                **{k: v for k, v in rec["props"].items() if k != "value"},
            }
        )
    edges = [
        {"source": rec["source"], "target": rec["target"], "type": rec["type"], **rec["props"]} for rec in edge_records
    ]
    return {"nodes": nodes, "edges": edges}


def subgraph(value: str, hops: int = 2, limit: int = 500) -> dict[str, list[dict[str, Any]]]:
    """Return the neighborhood around a node matched by ``value``."""
    s = get_settings()
    hops = min(max(hops, 1), s.graph_default_hops * 2)
    # Build the Cypher with the hops count spliced in via a placeholder, so the
    # Neo4j `$param` and `{value: ...}` tokens aren't disturbed by str formatting.
    cypher = (
        "MATCH (center {value: $value}) "
        f"CALL {{ WITH center MATCH (n)-[r*1..{hops}]-(center) RETURN DISTINCT n AS n }} "
        "WITH DISTINCT n LIMIT $limit "
        "RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props"
    )
    with session() as tx:
        node_records = tx.run(
            cypher,
            value=value,
            limit=limit,
        ).value()
        ids = [r["id"] for r in node_records]
        if not ids:
            return {"nodes": [], "edges": []}
        edge_records = tx.run(
            "MATCH (a)-[r]->(b) WHERE id(a) IN $ids AND id(b) IN $ids "
            "RETURN id(a) AS source, id(b) AS target, type(r) AS type, properties(r) AS props",
            ids=ids,
        ).value()

    nodes = []
    for rec in node_records:
        labels = [lb for lb in rec["labels"] if lb != "_Entity"]
        nodes.append(
            {
                "id": rec["id"],
                "label": labels[0] if labels else "Entity",
                "value": rec["props"].get("value", str(rec["id"])),
                **{k: v for k, v in rec["props"].items() if k != "value"},
            }
        )
    edges = [
        {"source": rec["source"], "target": rec["target"], "type": rec["type"], **rec["props"]} for rec in edge_records
    ]
    return {"nodes": nodes, "edges": edges}


def find_nodes(kind: str | None = None, query: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Search nodes by label and/or a value/description substring."""
    conditions: list[str] = []
    params: dict[str, Any] = {"limit": limit}
    if kind:
        params["label"] = canonical_label(kind)
        conditions.append("$label IN labels(n)")
    if query:
        params["q"] = f"(?i).*{query}.*"
        conditions.append("(n.value =~ $q OR coalesce(n.description,'') =~ $q)")
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    cypher = (
        f"MATCH (n:_Entity) {where} "
        "RETURN id(n) AS id, labels(n) AS labels, properties(n) AS props "
        "ORDER BY n.last_seen DESC LIMIT $limit"
    )
    with session() as tx:
        records = tx.run(cypher, **params).value()
    out = []
    for rec in records:
        labels = [lb for lb in rec["labels"] if lb != "_Entity"]
        out.append(
            {
                "id": rec["id"],
                "label": labels[0] if labels else "Entity",
                "value": rec["props"].get("value", str(rec["id"])),
                **{k: v for k, v in rec["props"].items() if k != "value"},
            }
        )
    return out


def clear_graph() -> dict[str, int]:
    """Wipe all nodes + edges. CLI only."""
    with session() as tx:
        nodes = tx.run("MATCH (n:_Entity) DETACH DELETE n RETURN count(n) AS c").single()["c"]
    return {"deleted": nodes}


# ──────────────────────────────────────────────────────────────────────────
# Process / skill retrieval (for the skills engine + API)
# ──────────────────────────────────────────────────────────────────────────


def get_process(value: str) -> dict[str, Any] | None:
    """Fetch a Process node + its full step/decision/policy neighborhood."""
    with session() as tx:
        proc = tx.run(
            "MATCH (p:Process {value: $value}) RETURN id(p) AS id, properties(p) AS props",
            value=value,
        ).single()
        if not proc:
            return None
        steps = tx.run(
            "MATCH (p:Process {value: $value})-[:HAS_STEP]->(s) "
            "OPTIONAL MATCH (s)-[:NEXT]->(nx) "
            "OPTIONAL MATCH (s)-[:USES]->(sys:System) "
            "OPTIONAL MATCH (s)-[:GOVERNED_BY]->(pol:Policy) "
            "RETURN id(s) AS id, properties(s) AS props, "
            "collect(DISTINCT sys.value) AS systems, "
            "collect(DISTINCT pol.value) AS policies",
            value=value,
        ).value()
        owner = tx.run(
            "MATCH (p:Process {value: $value})-[:OWNED_BY|EXECUTED_BY]->(r) "
            "RETURN collect(DISTINCT {kind: labels(r)[0], value: r.value}) AS owners",
            value=value,
        ).single()
        sources = tx.run(
            "MATCH (p:Process {value: $value})-[:EXTRACTED_FROM]->(d:Document) "
            "RETURN collect(DISTINCT {value: d.value, kind: d.kind, uri: coalesce(d.uri,'')}) AS sources",
            value=value,
        ).single()
    return {
        "process": {"id": proc["id"], **proc["props"]},
        "steps": [
            {
                "id": s["id"],
                **s["props"],
                "systems": s["systems"],
                "policies": s["policies"],
            }
            for s in steps
        ],
        "owners": owner["owners"] if owner else [],
        "sources": sources["sources"] if sources else [],
    }
