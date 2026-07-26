#!/usr/bin/env bash
# One-time local setup for SAAS AI.
#   - prepares a .env from the example if absent
#   - seeds a SearXNG settings.yml that allows the /search JSON API
#   - prints next steps
set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== SAAS AI setup ==="

# 1. .env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "[setup] created .env from .env.example (review it)"
else
  echo "[setup] .env already exists, leaving it"
fi

# 2. SearXNG settings enabling the JSON output the web provider needs.
#    Mounted into the searxng container at /etc/searxng.
SEARXNG_DIR="${SEARXNG_DIR:-./.searxng}"
mkdir -p "${SEARXNG_DIR}"
if [ ! -f "${SEARXNG_DIR}/settings.yml" ]; then
  cat > "${SEARXNG_DIR}/settings.yml" <<'YAML'
use_default_settings: true
server:
  bind_address: "0.0.0.0"
  secret_key: "saasai-dev-secret-change-me"
  limiter: false
  image_proxy: false
search:
  formats: [html, json]
outgoing:
  request_timeout: 10
  max_request_timeout: 15
YAML
  echo "[setup] wrote ${SEARXNG_DIR}/settings.yml (JSON search enabled)"
fi

cat <<'NEXT'

=== Setup complete ===

Next steps:
  1. Start the stack:        docker compose up -d
  2. Pull the models:        ./scripts/ollama_pull.sh
  3. Open the UI:            http://localhost:3000
  4. Browse the graph DB:    http://localhost:7474  (user neo4j / password from .env)

Without Docker, you can run the backend directly:
  python -m venv .venv && source .venv/bin/activate
  pip install -e ".[dev]"
  uvicorn app.main:app --reload --app-dir backend
NEXT
