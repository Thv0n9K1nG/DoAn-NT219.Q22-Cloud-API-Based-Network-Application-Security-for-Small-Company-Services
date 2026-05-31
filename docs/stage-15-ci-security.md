# Stage 15 CI/CD Security Automation

Stage 15 adds GitHub Actions automation for the checks that should block unsafe
changes before merge: unit tests, OPA policy tests, SAST, dependency scanning,
filesystem vulnerability scanning, Docker image builds, and manual DAST.

## Scope Implemented

- Added `.github/workflows/security.yml`.
  - Runs pytest and uploads `pytest-report.xml`.
  - Runs OPA policy tests through `scripts/test-opa.sh`.
  - Runs Bandit and Semgrep and uploads JSON reports.
  - Runs `pip-audit` for each Python requirements file.
  - Runs Trivy filesystem scan and uploads SARIF.
- Added `.github/workflows/build.yml`.
  - Builds `user-service`, `resource-service`, `admin-service`, and
    `payment-service` with a matrix.
  - Pushes to GHCR only on `main` branch pushes.
- Added `.github/workflows/dast.yml`.
  - Manual `workflow_dispatch` workflow for ZAP API scan against a provided
    OpenAPI URL.
  - Uploads `zap-report.json` and `zap-report.html`.
- Added `.github/dependabot.yml` for GitHub Actions and Python dependency PRs.
- Added `scripts/test-ci-security.sh` for local pre-push checks.
- Updated dev test/scanner dependencies in `requirements-dev.txt`.
- Added Bandit configuration in `pyproject.toml`.
- Annotated known Bandit false positives where constants are public identifiers,
  not credentials.

## CI Behavior

The security workflow runs automatically on pull requests and pushes to:

```text
main
develop
```

Expected blocking behavior:

- Unit test failures block merge.
- OPA policy test failures block merge.
- Bandit findings block merge unless explicitly annotated as false positives.
- Semgrep findings block merge.
- `pip-audit` findings block merge.
- Trivy high/critical findings block merge.

DAST is manual because it needs a reachable lab or staging target. The workflow
accepts a `target_url` input such as:

```text
https://staging.example.local/openapi.json
```

For the local lab, the target should be reachable from the GitHub runner or from
the machine executing ZAP.

## Local Test Commands

Install local dev dependencies:

```bash
python -m pip install -r requirements-dev.txt
```

Expected output includes:

```text
Requirement already satisfied
```

Run the local CI security script:

```bash
bash scripts/test-ci-security.sh
```

Expected output includes:

```text
58 passed
PASS: 14/14
JSON output written to file: tests/reports/bandit-report.json
No known vulnerabilities found
Stage 15 local CI security checks passed.
```

Run Semgrep through Docker:

```bash
docker run --rm -v "${PWD}:/src" -w /src semgrep/semgrep:1.100.0 semgrep scan \
  --config=p/python \
  --config=p/jwt \
  --config=p/secrets \
  --metrics=off \
  --error \
  --json \
  --output=tests/reports/semgrep-report.json \
  services shared scripts opa
```

Powershell version:

```powershell
docker run --rm -v "${PWD}:/src" -w /src semgrep/semgrep:1.100.0 semgrep scan `
  --config=p/python `
  --config=p/jwt `
  --config=p/secrets `
  --metrics=off `
  --error `
  --json `
  --output=tests/reports/semgrep-report.json `
  services shared scripts opa
```

Expected output includes:

```text
Ran 187 rules
0 findings
```

Validate GitHub workflow YAML:

```bash
python -c "import yaml, pathlib; [yaml.safe_load(p.read_text()) for p in pathlib.Path('.github').rglob('*.yml')]; print('github workflow yaml parse ok')"
```

Expected output:

```text
github workflow yaml parse ok
```

Build all service images:

```bash
docker compose build user-service resource-service admin-service payment-service
```

Expected output includes:

```text
Image nt219-cloud-api-security-user-service Built
Image nt219-cloud-api-security-resource-service Built
Image nt219-cloud-api-security-admin-service Built
Image nt219-cloud-api-security-payment-service Built
```

Validate Compose:

```bash
docker compose config --quiet
```

Expected output:

```text
no output and exit code 0
```

## DAST Notes

The DAST workflow is intentionally manual:

```text
Actions -> DAST API Scan -> Run workflow -> target_url=<OpenAPI URL>
```

Expected successful workflow artifacts:

```text
zap-report.json
zap-report.html
```

Local ZAP smoke testing was attempted with a temporary OpenAPI endpoint, but the
local Docker pull for the ZAP image timed out after several minutes. No
application test failed; this is recorded as an environment/tooling limitation.
Run the manual workflow or a local ZAP command when the ZAP image is available:

```bash
docker run --rm -v "${PWD}/tests/reports:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable zap-api-scan.py \
  -t "https://localhost:8443/openapi.json" \
  -f openapi \
  -J zap-report.json \
  -r zap-report.html \
  -I
```

Version can be run on Powershell:

```powershell
docker run --rm -v "${PWD}/tests/reports:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable zap-api-scan.py -t "https://localhost:8443/openapi.json" -f openapi -J zap-report.json -r zap-report.html -I
```

Use **host.docker.internal** instead of **localhost** because api run on host not in container

```powershell
docker run --rm -v "${PWD}/tests/reports:/zap/wrk:rw" ghcr.io/zaproxy/zaproxy:stable zap-api-scan.py -t "https://host.docker.internal:8443/openapi.json" -f openapi -J zap-report.json -r zap-report.html -I -z "-config network.https.checkCertificate=false"
```

Use a reachable OpenAPI URL. If the gateway uses self-signed TLS and ZAP cannot
connect, scan a staging URL or an internal HTTP OpenAPI endpoint for the DAST
job.

## Security Notes

- GitHub workflows do not include real Stripe, Vault, Keycloak, or certificate
  secrets.
- Reports are written under `tests/reports/`, which is ignored except for
  `.gitkeep`.
- `gateway/kong.yml`, `.env`, private keys, and generated certificates remain
  excluded from Git.
- Semgrep registry metrics are disabled in the workflow command with
  `--metrics=off`.
- Dependabot opens PRs instead of silently changing dependencies.

## Verification Performed

Commands run locally:

```text
python -m pip install -r requirements-dev.txt
bash scripts/test-ci-security.sh
python -m pip_audit -r requirements-dev.txt
docker run --rm -v "${PWD}:/src" -w /src semgrep/semgrep:1.100.0 semgrep scan ...
docker compose build user-service resource-service admin-service payment-service
python -c "... yaml.safe_load(...) ..."
```

Observed results:

```text
pytest: 58 passed
OPA: PASS 14/14
Bandit: 0 findings after false-positive annotations
pip-audit: No known vulnerabilities found
Semgrep: 0 findings
Docker build: all four service images built
Workflow YAML: parsed successfully
ZAP local smoke: blocked by local image pull timeout
```

## Files Added or Changed

- `.github/workflows/security.yml`
- `.github/workflows/build.yml`
- `.github/workflows/dast.yml`
- `.github/dependabot.yml`
- `scripts/test-ci-security.sh`
- `requirements-dev.txt`
- `pyproject.toml`
- `services/payment-service/app/services/payment_service.py`
- `shared/errors.py`
- `shared/s2s_token.py`

## Completion Criteria

Stage 15 is complete when:

- Pull requests run automated unit, OPA, SAST, dependency, and build checks.
- Reports are uploaded as GitHub Actions artifacts.
- Docker service images build in the CI matrix.
- DAST can be launched manually against a reachable OpenAPI target.
- Local pre-push checks pass through `scripts/test-ci-security.sh`.
