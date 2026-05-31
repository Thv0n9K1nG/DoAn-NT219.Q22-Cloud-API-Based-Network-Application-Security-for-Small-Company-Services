# Stage 15 TUNE: Build Workflow and Local ZAP Scan Fixes

This tuning pass fixes two issues found after Stage 15 was pushed and tested:

1. The Docker Build GitHub Action failed for all four service images.
2. The documented local ZAP command could not find `openapi.json`.

## 1. GitHub Actions Docker Build Failure

### Evidence

The four uploaded action logs showed the same error pattern for:

- `user-service`
- `resource-service`
- `admin-service`
- `payment-service`

Representative log line:

```text
ERROR: failed to build: invalid tag "ghcr.io/Thv0n9K1nG/nt219-user-service:<sha>": repository name must be lowercase
```

The workflow used:

```yaml
tags: ghcr.io/${{ github.repository_owner }}/nt219-${{ matrix.service }}:${{ github.sha }}
```

`github.repository_owner` preserved uppercase characters from the GitHub owner
name. Docker image repository names must be lowercase, so Buildx rejected the
tag before building any service image.

### Fix

`.github/workflows/build.yml` now computes a lowercase GHCR tag in a Bash step:

```yaml
- name: Compute lowercase image tag
  id: image
  shell: bash
  env:
    SERVICE_NAME: ${{ matrix.service }}
  run: |
    owner="$(printf '%s' "$GITHUB_REPOSITORY_OWNER" | tr '[:upper:]' '[:lower:]')"
    echo "tag=ghcr.io/${owner}/nt219-${SERVICE_NAME}:${GITHUB_SHA}" >> "$GITHUB_OUTPUT"
```

The Docker build step now uses:

```yaml
tags: ${{ steps.image.outputs.tag }}
```

For PR/develop builds, the workflow also uses `load: true` so the Buildx result
is materialized locally instead of only staying in the BuildKit cache. For `main`
pushes, the workflow still pushes to GHCR.

### Verification

Local Buildx verification with a lowercase GHCR tag:

```bash
docker buildx build --file services/user-service/Dockerfile --tag ghcr.io/thv0n9k1ng/nt219-user-service:stage15-tune --load .
```

Expected output:

```text
naming to ghcr.io/thv0n9k1ng/nt219-user-service:stage15-tune
DONE
```

Observed output:

```text
naming to ghcr.io/thv0n9k1ng/nt219-user-service:stage15-tune 0.0s done
DONE 0.6s
```

## 2. Local ZAP Could Not Find `openapi.json`

### Root Cause

The previous documentation pointed ZAP at:

```text
https://localhost:8443/openapi.json
https://host.docker.internal:8443/openapi.json
```

That URL is not valid for this lab because Kong routes business API paths such
as `/api/v1/resources`, `/api/v1/payments`, and `/webhooks/stripe`. It does not
route a root `/openapi.json` endpoint. The FastAPI services do expose
`/openapi.json`, but those service ports are internal behind Kong.

### Fix

Added:

- `scripts/generate-zap-openapi.py`
- `scripts/test-zap-local.ps1`

The generator writes a gateway-facing OpenAPI document to:

```text
tests/reports/zap-openapi.json
```

The PowerShell script:

1. Generates the OpenAPI file with server URL `https://host.docker.internal:8443`.
2. Starts a temporary local static server on `127.0.0.1:18090`.
3. Runs ZAP inside Docker against:

```text
http://host.docker.internal:18090/zap-openapi.json
```

4. Passes `-O https://host.docker.internal:8443` so ZAP scans Kong, not the
   temporary static file server.
5. Disables certificate validation for the lab self-signed TLS certificate.

### Command

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-zap-local.ps1
```

Optional custom gateway URL:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-zap-local.ps1 -GatewayUrl "https://host.docker.internal:8443"
```

### Expected Output

```text
wrote ...\tests\reports\zap-openapi.json server_url=https://host.docker.internal:8443
Running ZAP against OpenAPI spec: http://host.docker.internal:18090/zap-openapi.json
Gateway target declared in spec: https://host.docker.internal:8443
Using override, new target: https://host.docker.internal:8443
Number of Imported URLs: 11
FAIL-NEW: 0
```

### Observed Output

The local ZAP scan completed successfully:

```text
Total of 45 URLs
FAIL-NEW: 0
WARN-NEW: 2
2026-05-31 14:55:44,335 Using override, new target: https://host.docker.internal:8443
2026-05-31 14:55:44,337 Number of Imported URLs: 11
```

ZAP reported two warnings:

```text
WARN-NEW: Strict-Transport-Security Header Not Set [10035]
WARN-NEW: Server Leaks Version Information via "Server" HTTP Response Header Field [10036]
```

These are valid DAST findings on the current lab gateway:

- HSTS is not currently configured on Kong responses.
- Kong/upstream responses still expose a `Server` header.

They are not command failures. They should either be fixed in a later hardening
pass or documented as accepted lab limitations if time is limited.

## 3. DAST Workflow Tune

`.github/workflows/dast.yml` now supports an optional `target_override` input:

```text
target_url       = OpenAPI document URL reachable by ZAP
target_override  = API base URL that replaces servers from the OpenAPI document
```

This mirrors the local `-O` behavior and supports the pattern:

```text
OpenAPI spec served from one URL, API gateway scanned at another URL.
```

## Files Changed

- `.github/workflows/build.yml`
- `.github/workflows/dast.yml`
- `scripts/generate-zap-openapi.py`
- `scripts/test-zap-local.ps1`
- `docs/stage-15-ci-security.md`
- `docs/stage-15-TUNE.md`

## Re-Test Checklist

Run:

```bash
python -c "import yaml, pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github').rglob('*.yml')]; print('github workflow yaml parse ok')"
docker buildx build --file services/user-service/Dockerfile --tag ghcr.io/thv0n9k1ng/nt219-user-service:stage15-tune --load .
```

Run on PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test-zap-local.ps1
```

Expected result:

```text
Workflow YAML parses successfully.
Lowercase GHCR image tag builds successfully.
ZAP imports generated OpenAPI and scans Kong through host.docker.internal.
FAIL-NEW: 0
```
