#!/usr/bin/env bash
# Run the lint + type-check suite. Mirrors CI.
set -euo pipefail
cd "$(dirname "$0")/.."

failed=0

echo "=== ruff format --check ==="
ruff format --check backend || failed=1

echo "=== ruff check ==="
ruff check backend || failed=1

echo "=== mypy ==="
mypy backend --config-file pyproject.toml || failed=1

if [ "${failed}" -ne 0 ]; then
  echo "❌ validation failed"
  exit 1
fi
echo "✅ all checks passed"
