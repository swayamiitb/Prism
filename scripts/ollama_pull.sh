#!/usr/bin/env bash
# Pull the local models Context Brain needs (gemma4:12b reasoning brain + bge-m3 embedder).
# Run once after `docker compose up -d`. Models persist in the ollama-models volume.
#
# Usage:
#   ./scripts/ollama_pull.sh              # pull both default models
#   OLLAMA_CHAT_MODEL=gemma4:26b-a4b ./scripts/ollama_pull.sh
set -euo pipefail

CHAT_MODEL="${OLLAMA_CHAT_MODEL:-gemma4:12b}"
EMBED_MODEL="${OLLAMA_EMBED_MODEL:-bge-m3}"
HOST="${OLLAMA_HOST:-http://localhost:11434}"

# If the API service is running under compose, talk to the container directly;
# otherwise fall back to the local Ollama.
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^saasai-ollama$'; then
  echo "[pull] using container saasai-ollama"
  run() { docker exec saasai-ollama ollama pull "$1"; }
else
  echo "[pull] using host Ollama at ${HOST}"
  run() { ollama pull "$1"; }
fi

echo "[pull] >>> ${CHAT_MODEL} (this is several GB; grab a coffee)"
run "${CHAT_MODEL}"
echo "[pull] >>> ${EMBED_MODEL}"
run "${EMBED_MODEL}"

echo "[pull] done. Verify with: docker exec saasai-ollama ollama list"
