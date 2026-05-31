#!/bin/bash
set -euo pipefail

mkdir -p tests/reports
PYTHON_BIN="${PYTHON_BIN:-python}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python.exe >/dev/null 2>&1; then
    PYTHON_BIN="python.exe"
  elif command -v py >/dev/null 2>&1; then
    PYTHON_BIN="py"
  else
    echo "Python interpreter not found. Set PYTHON_BIN to your Python executable." >&2
    exit 127
  fi
fi

echo "=== Python tests ==="
"$PYTHON_BIN" -m pytest -v --tb=short --junitxml=tests/reports/pytest-report.xml

echo "=== OPA policy tests ==="
bash scripts/test-opa.sh

echo "=== Bandit SAST ==="
"$PYTHON_BIN" -m bandit -c pyproject.toml -r services shared -f json -o tests/reports/bandit-report.json

echo "=== pip-audit dependency scan ==="
for req in requirements-dev.txt services/*/requirements.txt; do
  report="tests/reports/pip-audit-$(echo "$req" | tr '/.' '--').json"
  "$PYTHON_BIN" -m pip_audit -r "$req" --format=json --output "$report"
done

echo "=== Compose validation ==="
docker compose config --quiet

echo "Stage 15 local CI security checks passed."
