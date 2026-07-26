# Setup

## Prerequisites

- **Docker** + **Docker Compose** (recommended — runs everything)
- **Ollama** either in the stack (handled by compose) or installed locally for GPU acceleration
- ~20 GB free for the models (qwen3:14b is ~9 GB; bge-m3 is ~1.2 GB) and graph data
- For GPU inference on Linux: an NVIDIA GPU with ≥ 12 GB VRAM. CPU inference works but is slower.

## Option A — Docker (recommended)

```bash
cp .env.example .env
./scripts/setup.sh
docker compose up -d
./scripts/ollama_pull.sh
```

Then open:
- **UI:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **Neo4j:** http://localhost:7474 (user `neo4j`, password from `.env`)

### First-run notes

- The API service waits for Neo4j, Ollama, and SearXNG to be healthy before starting (`depends_on: condition: service_healthy`).
- The model pull is the slow step. `./scripts/ollama_pull.sh` pulls into the `ollama-models` volume, so it persists across restarts.
- If you change `OLLAMA_CHAT_MODEL` in `.env`, re-run `ollama_pull.sh` with that var set.

## Option B — local backend (no Docker for the app)

Use this if you already run Neo4j + Ollama, or want hot-reload without rebuilding images.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"

# Have Neo4j + Ollama running somewhere; point .env at them.
cd backend
PYTHONPATH=. uvicorn app.main:app --reload      # API on :8000
PYTHONPATH=. python -m saas_ai chat             # or the CLI
```

For the frontend, `cd frontend && npm install && npm run dev` (needs Node 20).

## Configuration

All knobs live in `.env` (see `.env.example` for the full catalogue). The load-bearing ones:

| var | default | purpose |
|---|---|---|
| `OLLAMA_CHAT_MODEL` | `qwen3:14b` | reasoning brain (swap for `qwen3:30b-a3b` on stronger hardware) |
| `OLLAMA_EMBED_MODEL` | `bge-m3` | node embeddings for semantic search |
| `NEO4J_URI` / `NEO4J_PASSWORD` | `bolt://localhost:7687` / `saasai-dev-password` | graph DB |
| `SEARXNG_URL` | `http://localhost:8080` | web search backend |
| `GITHUB_TOKEN` | _(empty)_ | optional; raises GitHub rate limits 60→5000/hr |
| `GRAPH_DEFAULT_HOPS` | `2` | neighborhood depth for connection queries |
| `GRAPH_MIN_CONFIDENCE` | `0.3` | edge confidence floor |

## Troubleshooting

- **`graph unavailable` in the UI / providers show `✗` for graph** — Neo4j isn't up. `docker compose ps neo4j`, check logs with `docker compose logs neo4j`.
- **Agent answers are slow / time out** — the first qwen3:14b inference loads the model into memory (~30s). Subsequent turns are faster. On CPU, expect several seconds per turn.
- **Web provider `✗`** — SearXNG needs its `settings.yml` with `formats: [html, json]`. `./scripts/setup.sh` writes one; if you skipped it, the JSON API won't respond.
- **GitHub `60 req/hr` limit** — set `GITHUB_TOKEN` to a fine-grained PAT with public-read.
