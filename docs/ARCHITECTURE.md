# Architecture

SAAS AI is an OSINT graph-intelligence agent. This doc covers the agent model, the data model, and the request flow.

## The agent model

```
                         ┌─────────────────────────────────────────────┐
   Next.js UI ─────────▶ │   FastAPI                                    │
   (3D/2D graph, chat)   │   /chat (SSE)  /graph  /ingest  /providers  │
                         └───────────────┬─────────────────────────────┘
                                         │
                          ┌──────────────▼──────────────┐
                          │  Orchestrator (LangGraph)    │  one LLM hop/turn
                          │  qwen3:14b via ChatOllama     │  routes → reasons → answers
                          └───┬───────┬───────┬───────┬───┘
                              │       │       │       │
                   ┌──────────▼┐ ┌────▼───┐ ┌─▼─────┐ ┌▼──────────┐
                   │  Graph     │ │  Web   │ │Domain │ │  GitHub   │  Context
                   │  (r/w)     │ │        │ │/DNS/  │ │           │  Providers
                   │  Neo4j     │ │SearXNG │ │WHOIS/ │ │ PyGithub  │  (sub-agents)
                   └────────────┘ │+Traf.  │ │ SSL)  │ │           │
                                  └────────┘ └───────┘ └───────────┘
```

### Orchestrator

A LangGraph `create_react_agent` bound to the local qwen3:14b model. Its tools are:

- `list_providers` — meta-tool showing live provider status.
- `query_<id>` for every provider.
- `update_graph` — the **only** write tool (graph provider only).

The system prompt (`saas_ai/instructions.py: SAAS_AI_INSTRUCTIONS`) enforces routing rules, response shape, citation discipline, prompt-injection resistance, and the public-OSINT-only constraint. It takes one reasoning step per turn.

### Context providers

Each provider is a `ContextProvider` subclass (`saas_ai/providers/base.py`) exposing:

| method | purpose |
|---|---|
| `query(question)` / `aquery` | read from the source; return an `Answer` of `Document`s |
| `aupdate(instruction)` | optional write path; base returns a clean "read-only" error |
| `status()` | health check (`Status{ok, detail}`) |
| `get_tools()` | builds the `query_<id>` (+ `update_<id>`) LangChain tools |

Providers isolate source-specific quirks (DNS timeouts, GitHub pagination, SearXNG JSON shape) from the orchestrator's context — the agent only sees clean `query_<id>`/`update_<id>` tools.

### The single-write surface

Only the graph provider writes to Neo4j. The flow:

1. A collection provider returns `Document`s, each optionally carrying structured `entities` (node/edge specs).
2. The orchestrator (or `/ingest`) passes them to the graph-writer.
3. The graph-writer asks qwen3 to emit a `GraphPlan` (strict JSON), **validates it** with pydantic (`NodeSpec`/`EdgeSpec` reject unknown kinds/types), then applies it via `upsert_node` / `upsert_edge`.

No raw LLM output ever reaches the database.

## The data model

### Nodes

Every node carries the `_Entity` label (for cross-type indexing) plus one canonical label:

| label | `value` (natural key) | example |
|---|---|---|
| `Domain` | lowercased domain | `github.com` |
| `Subdomain` | lowercased hostname | `api.github.com` |
| `IPAddress` | IPv4/IPv6 | `140.82.112.3` |
| `Organization` | org name | `GitHub, Inc.` |
| `Person` | person name | `Linus Torvalds` |
| `Email` | email address | `octocat@github.com` |
| `GitHubUser` | login | `torvalds` |
| `GitHubRepo` | `owner/repo` | `torvalds/linux` |
| `WebPage` | URL | `https://example.com/about` |
| `Certificate` | CN + expiry | `example.com (2026-12-01)` |
| `Tag` | tag name | `critical-infra` |

Common properties: `description`, `source`, `confidence` (0.0–1.0), `first_seen`, `last_seen`, plus provider-specific fields.

### Edges

`RESOLVES_TO`, `SUBDOMAIN_OF`, `REGISTERED_BY`, `HAS_CERTIFICATE`, `OWNS`, `MEMBER_OF`, `AUTHORED`, `LINKS_TO`, `MENTIONED_ON`, `EXTRACTED_FROM`, `TAGGED` — each with `source`, `confidence`, `first_seen`, `last_seen`.

### Constraints

Each label has a uniqueness constraint on `value` (so re-merging a node updates rather than duplicates). A `_Entity` label index + `first_seen` index speed the common read paths. `ensure_schema()` creates them idempotently at startup.

## Request flow

### Chat (`POST /chat/stream`)

1. Frontend opens an SSE connection with the user message.
2. The orchestrator agent runs; `astream_events` yields token chunks, tool-start events, and a final done event.
3. Each tool call hits a provider; results flow back into the agent's context.
4. As the agent files findings via `update_graph`, the graph mutates.
5. The frontend's `done` handler re-fetches `/graph` so the 3D view updates live.

### Ingest (`POST /ingest`)

Bypasses the LLM for speed. Runs each collection provider's `aquery(target)` directly, then applies the returned `entities` to the graph via the same validated write path. Returns counts of filed nodes/edges.

### Graph (`GET /graph`)

Returns the whole graph (capped at `limit` nodes, default 2000) as `{nodes, edges}` for the frontend. Nodes carry `id` (Neo4j internal id), `label`, `value`, and all properties; edges carry `source`/`target` ids + `type`. The frontend maps labels → colors via a shared palette.

## Why this shape

The design follows a deliberately conservative agent architecture — a single
orchestrator with isolated context providers, one reasoning step per turn,
autonomous graph-based memory, and a single validated write surface. Every
layer is open source and self-contained: no hosted control plane, no cloud
model calls, no proprietary SDKs. The result is a platform that's auditable
(closed vocabulary, strict plan validation), private (runs entirely on your own
hardware), and built for graph-based security analysis.
