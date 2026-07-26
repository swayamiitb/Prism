# Evaluation

SAAS AI ships a tiered eval harness that locks in the architecture's
load-bearing guarantees and verifies agent behavior.

## Tiers

### 1. Wiring invariants (deterministic, no LLM, <1s)

```bash
python -m evals wiring
```

Eight structural checks that lock in the architecture's guarantees:

| id | name | what it asserts |
|---|---|---|
| w1 | orchestrator tool surface | `list_providers` + every `query_<id>`/`update_graph` present; no outbound tools |
| w2 | single write surface | only the graph provider is writable; collection providers are read-only |
| w3 | provider protocol shape | every provider is a `ContextProvider` with id/name + query/status/get_tools |
| w4 | graph vocabulary closed | node/edge normalisation works; unknown kinds rejected |
| w5 | read-only update is clean | a read-only provider's `update_*` returns a clean error, not a crash |
| w6 | graph plan schema strict | `NodeSpec`/`EdgeSpec` reject unknown kinds + out-of-range confidence |
| w7 | target extraction | the graph provider's target extractor handles domain/IP/@handle/quoted |
| w8 | API routes registered | `/health`, `/providers`, `/chat`, `/graph`, `/ingest` all present |

These must always be green. Run them before merging anything that touches the agent, providers, or API.

### 2. Behavioral cases (LLM-driven)

Agent behavior frozen into cases with substring/regex/tool assertions. Requires a live stack (Ollama + Neo4j). Each case:

- sends a prompt to the orchestrator,
- asserts the response contains/forbids substrings, matches regexes, and that the expected tools were called,
- supports multi-turn follow-ups in the same session.

Cases cover: routing (single + multi-provider), graph write/read round-trips, graceful degradation (provider errors), empty-result handling, curation over dumping, prompt-injection resistance, and multi-turn recall.

### 3. LLM-as-judge (LLM-scored)

Rubric-scored cases where a substring assertion is too brittle (citation quality, conciseness, multi-provider attribution). The judge runs on the same local qwen3 model.

## Running

```bash
# Always-green, no deps:
python -m evals wiring

# Needs the stack up (docker compose up -d + ollama_pull.sh):
python -m evals behavioral
```

## The fix loop

When a case fails, classify the failure before patching:

- **Agent bug** → fix `instructions.py` (prompt) or the provider.
- **Stale assertion** → the behavior changed intentionally; update the case.
- **Runner bug** → fix `evals/runner.py`.

Never weaken an assertion just to green it. Commit one fix per commit.
