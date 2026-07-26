#!/usr/bin/env bash
# Format + auto-fix imports.
set -euo pipefail
cd "$(dirname "$0")/.."
ruff format backend
ruff check --select I --fix backend
echo "✅ formatted"
