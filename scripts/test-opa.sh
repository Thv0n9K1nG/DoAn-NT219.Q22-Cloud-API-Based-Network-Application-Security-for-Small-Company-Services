#!/bin/bash
set -euo pipefail

if command -v opa >/dev/null 2>&1; then
  exec opa test opa/policies opa/tests opa/data -v
fi

# Docker fallback keeps policy tests reproducible on developer machines without a local OPA binary.
exec docker run --rm \
  -v "$PWD/opa:/workspace/opa:ro" \
  openpolicyagent/opa:0.65.0 \
  test /workspace/opa/policies /workspace/opa/tests /workspace/opa/data -v
