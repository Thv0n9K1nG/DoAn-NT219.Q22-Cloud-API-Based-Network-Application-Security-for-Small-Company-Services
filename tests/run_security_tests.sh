#!/bin/bash
set -euo pipefail

mkdir -p tests/reports

if command -v python.exe >/dev/null 2>&1; then
  PYTHON_BIN=python.exe
elif command -v py >/dev/null 2>&1; then
  PYTHON_BIN="py -3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
else
  echo "Python was not found on PATH" >&2
  exit 1
fi

echo "=== OPA Policy Tests ==="
bash scripts/test-opa.sh

echo "=== Unit Regression Tests ==="
$PYTHON_BIN -m pytest services tests/test_*.py -v --tb=short --junitxml=tests/reports/security-unit-report.xml

echo "=== Attack Simulations ==="
$PYTHON_BIN -m pytest tests/attacks -v --tb=short --junitxml=tests/reports/security-attack-report.xml

echo "=== ZAP API Scan ==="
if command -v pwsh >/dev/null 2>&1; then
  pwsh -ExecutionPolicy Bypass -File scripts/test-zap-local.ps1 || echo "ZAP scan failed or was skipped; inspect tests/reports/zap-report.*"
elif command -v powershell >/dev/null 2>&1; then
  powershell -ExecutionPolicy Bypass -File scripts/test-zap-local.ps1 || echo "ZAP scan failed or was skipped; inspect tests/reports/zap-report.*"
elif command -v powershell.exe >/dev/null 2>&1; then
  powershell.exe -ExecutionPolicy Bypass -File scripts/test-zap-local.ps1 || echo "ZAP scan failed or was skipped; inspect tests/reports/zap-report.*"
else
  echo "PowerShell was not found; skipping local ZAP scan."
fi

echo "=== Security tests complete ==="
