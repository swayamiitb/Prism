#!/usr/bin/env bash
# SAAS API container entrypoint.
# Waits for Neo4j + Ollama if WAIT_FOR_DEPS is set, then execs the command.
set -euo pipefail

wait_for() {
  local name="$1" url="$2"
  echo "[entrypoint] waiting for ${name} at ${url} ..."
  local i=0
  until curl -sf -o /dev/null "${url}" 2>/dev/null; do
    i=$((i + 1))
    if [ "${i}" -gt 60 ]; then
      echo "[entrypoint] WARNING: ${name} not reachable after 60s — continuing anyway." >&2
      return 0
    fi
    sleep 2
  done
  echo "[entrypoint] ${name} is up."
}

if [ "${WAIT_FOR_DEPS:-false}" = "true" ]; then
  # Neo4j's Bolt port doesn't answer HTTP/curl — check its HTTP port (7474) instead.
  NEO4J_HTTP="${NEO4J_HTTP_URL:-http://neo4j:7474}"
  wait_for "Neo4j"  "${NEO4J_HTTP}" 2>/dev/null || true
  wait_for "Ollama" "${OLLAMA_HOST:-http://localhost:11434}/api/tags"
  wait_for "SearXNG" "${SEARXNG_URL:-http://localhost:8080}/healthz" 2>/dev/null || true
fi

echo "[entrypoint] starting: $*"
exec "$@"
