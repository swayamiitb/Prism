# AGENTS.md — contributor guide

Context Brain is an AI that understands how a company works end-to-end and
turns that understanding into executable skills. This doc explains the
architecture so contributors (human or AI) can work on it without breaking the
load-bearing guarantees.

## Project overview

A single **orchestrator** (LangGraph ReAct loop, `gemma4:12b` via Ollama)
routes each turn to N **context providers** — sub-agents that each own one
company knowledge source. It synthesizes what it learns into the Neo4j
knowledge graph (the living map of how the company works) and exports
executable `.skill.yml` files.

### Context providers (the registry)

| id | provider | writable | what it does |
|---|---|---|---|
| `brain` | `BrainProvider` | **yes** | reads + writes the knowledge graph; synthesizes processes; exports skills (`query_brain` / `update_brain`) |
| `wiki` | `WikiProvider` | yes | local markdown wiki (policies, runbooks, decisions) (`query_wiki` / `update_wiki`) |
| `slack` | `SlackProvider` | no | historical Slack threads — where day-to-day know-how lives (`query_slack`) |
| `drive` | `DriveProvider` | no | company docs — design docs, process docs (`query_drive`) |

Providers register in `context_brain/contexts.py`. All run on seeded local
data by default; real Slack/Drive light up when their env vars are set.

### The single-write-surface principle

**Only `update_brain` mutates the database.** Source providers (slack/drive)
return `Document` results; the orchestrator funnels them through the
skills engine, which asks the model for a validated `SkillPlan`, checks it
against the closed vocabulary, and applies it. Raw LLM output never reaches
the DB.

## Architecture rules

- **One reasoning step per turn.** Read the question, call the minimal sources,
  synthesize, answer. No unbounded planning loops.
- **Synthesize, don't just retrieve.** When asked "how do we handle X", produce
  a Process (Steps/Decisions/Policies/owners/systems), not a list of links.
- **Provenance is first-class.** Every synthesized node links to the source
  document/thread via `EXTRACTED_FROM`. Cite where knowledge came from.
- **Closed graph vocabulary.** Node labels and edge types live in
  `graph_schema.NODE_LABELS` / `EDGE_TYPES`. Adding one is a deliberate change.
- **Local models only.** `gemma4:12b` (<31B) via Ollama. Company data is
  sensitive — don't add a hosted-model dependency.

## Key files

- `backend/context_brain/settings.py` — env config + `default_model()` (gemma4).
- `backend/context_brain/instructions.py` — orchestrator + brain sub-agent prompts.
- `backend/context_brain/agent.py` — LangGraph orchestrator, tool collection, streaming.
- `backend/context_brain/graph_schema.py` — company knowledge model + Neo4j read/write.
- `backend/context_brain/skills_engine.py` — synthesis plan → graph + `.skill.yml` export.
- `backend/context_brain/contexts.py` — provider registry.
- `backend/context_brain/providers/base.py` — the `ContextProvider` contract.
- `backend/context_brain/providers/{brain,wiki,slack,drive}.py` — the providers.
- `backend/app/main.py` + `router.py` — FastAPI surface (chat, graph, processes, skills).
- `backend/data/northwind/` — seeded sample company data.
- `backend/evals/wiring.py` — the 8 architecture invariants (must stay green).

## Commands

```bash
./scripts/setup.sh                 # first-time local setup
docker compose up -d               # boot the stack
./scripts/ollama_pull.sh           # pull gemma4:12b + bge-m3

./scripts/validate.sh              # ruff + mypy (what CI runs)
python -m pytest backend/tests -q  # unit + seed-data tests
python -m evals wiring             # architecture invariants

# from backend/, with PYTHONPATH=.
python -m context_brain chat | providers | graph-stats | skills
uvicorn app.main:app --reload
```

## Don't

- Don't write to Neo4j outside the brain provider / skills engine.
- Don't run raw LLM output against the DB — always go through the validated `SkillPlan`.
- Don't add a hosted-model or paid-API dependency.
- Don't merge if `./scripts/validate.sh`, `pytest`, or `python -m evals wiring` fail.
