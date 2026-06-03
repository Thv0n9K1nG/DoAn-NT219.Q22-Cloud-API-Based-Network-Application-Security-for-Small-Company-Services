# Kich ban demo localhost - NT219

Muc tieu: demo toan bo he thong tren may local qua Kong HTTPS `https://localhost:8443`, khong goi truc tiep service port noi bo.

Dung file nay khi:

- Ban demo tren laptop/phong lab.
- Chua co domain public san sang.
- Muon chung minh nhanh cac security controls va log trong Grafana local.

Neu thay yeu cau deploy Internet that, dung `demo/DEMO.md`. Neu thay cho phep demo local de kiem tra ky thuat, dung file nay.

## 0. Cau noi mo dau

> Day la ban demo local cua cung mot he thong. Client van khong goi truc tiep microservice, ma di qua Kong tren `https://localhost:8443`. Keycloak, OPA, Redis, PostgreSQL, Vault, Loki va Grafana deu chay bang Docker Compose. Cac control duoc demo giong ban public: JWT, OPA authorization, tenant isolation, BOLA protection, WAF-lite, rate limit, Stripe webhook verification, mTLS noi bo va ML-DSA assertion tren duong Kong -> service.

## 1. Chuan bi stack local

Mo terminal tai root repo:

```bash
cd /path/to/DoAn-NT219.Q22-Cloud-API-Based-Network-Application-Security-for-Small-Company-Services
```

Neu chay tren Windows PowerShell, van nen dung Git Bash syntax cho cac script `.sh`.

Sinh cert va ML-DSA upstream assertion:

```bash
bash scripts/generate-dev-certs.sh
```

Bat cac service chinh:

```bash
docker compose up -d postgres redis vault keycloak opa
bash scripts/keycloak-init.sh
bash scripts/kong-init.sh
docker compose up -d --build user-service resource-service admin-service payment-service kong
```

Bat observability de xem log tren Grafana:

```bash
docker compose --profile observability up -d loki grafana promtail
```

Kiem tra:

```bash
docker compose ps
```

Can thay:

```text
kong                    healthy/running
keycloak                running
opa                     healthy/running
user-service            healthy/running
resource-service        healthy/running
admin-service           healthy/running
payment-service         healthy/running
postgres                healthy/running
redis                   healthy/running
vault                   healthy/running
loki                    healthy/running
grafana                 healthy/running
promtail                running
```

## 2. Bien moi truong quan trong cho localhost

Neu `.env` cua ban co:

```text
KEYCLOAK_URL=http://keycloak:8080
```

thi day la URL dung ben trong Docker network. Khi lay token tu terminal host, phai override ve:

```bash
KEYCLOAK_URL=http://localhost:18080
```

Viec nay rat quan trong. Neu khong override, ban se gap loi:

```text
curl: (6) Could not resolve host: keycloak
```

Voi Git Bash, chay lenh theo mau:

```bash
KEYCLOAK_URL=http://localhost:18080 bash <script-name>.sh
```

## 3. Smoke test localhost

Chay:

```bash
KEYCLOAK_URL=http://localhost:18080 bash scripts/internet-smoke-test.sh https://localhost:8443
```

Expected:

```text
Smoke testing https://localhost:8443
gateway rejects missing token                    expected=401 actual=401
tenant user lists resources                      expected=200 actual=200
tenant user denied admin route                   expected=403 actual=403
non-json write rejected                          expected=415 actual=415
forged Stripe webhook rejected                   expected=400 actual=400
Internet smoke test passed.
```

Noi voi thay:

> Du la localhost, request van di qua HTTPS gateway `localhost:8443`. Em khong goi truc tiep port cua service.

## 4. Demo tong the bang script

Chay:

```bash
KEYCLOAK_URL=http://localhost:18080 bash demo/demo-script.sh https://localhost:8443
```

Expected nhung dong quan trong:

```text
GET /api/v1/resources without token -> 401
beta GET alpha resource -> 403
alpha user GET admin tenants -> 403
POST without application/json -> 415
20 200
5 429
forged webhook -> 400
valid token tenant_id: 11111111-1111-1111-1111-111111111111
tampered token rejected: Invalid S2S token signature
```

Giai thich tung dong:

- `401`: Gateway reject request khong co JWT.
- `403` BOLA: Beta tenant co token hop le nhung khong doc duoc resource cua Alpha tenant.
- `403` admin: Tenant user khong du role vao admin API, bi OPA/Kong chan.
- `415`: WAF-lite chan write request khong co `application/json`.
- `429`: Rate limit theo tenant da hoat dong.
- `400`: Stripe webhook gia mao bi reject.
- ML-DSA: token hop le verify duoc, token bi sua bi reject.

## 5. Demo JWT claims

Lay token:

```bash
TOKEN="$(KEYCLOAK_URL=http://localhost:18080 bash scripts/get-token.sh alpha-user@example.com "${KEYCLOAK_LAB_USER_PASSWORD:-TestPass123!}" | tr -d '\r\n')"
export TOKEN
```

Decode payload:

```bash
python - <<'PY'
import base64
import json
import os

token = os.environ["TOKEN"]
payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
print(json.dumps({
    "sub": claims.get("sub"),
    "tenant_id": claims.get("tenant_id"),
    "aud": claims.get("aud"),
    "roles": claims.get("realm_access", {}).get("roles", []),
    "iss": claims.get("iss"),
    "exp": claims.get("exp"),
}, indent=2))
PY
```

Can chi ra:

- `tenant_id`: dung cho tenant isolation.
- `roles`: dung cho RBAC/OPA.
- `aud=saas-api`: token dung audience.
- `iss=http://localhost:18080/realms/saas-platform`: issuer local.

## 6. Demo tung request thu cong

### 6.1. Khong token bi reject

```bash
curl -k -i https://localhost:8443/api/v1/resources
```

Expected:

```text
HTTP/1.1 401
```

### 6.2. Alpha tenant doc resource cua minh

```bash
curl -k -s https://localhost:8443/api/v1/resources \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Expected: JSON resource list cua Alpha.

### 6.3. Tenant user bi chan khoi admin route

```bash
curl -k -i https://localhost:8443/api/v1/admin/tenants \
  -H "Authorization: Bearer $TOKEN"
```

Expected:

```text
HTTP/1.1 403
```

### 6.4. WAF-lite chan content type sai

```bash
curl -k -i -X POST https://localhost:8443/api/v1/resources \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"bad-content-type"}'
```

Expected:

```text
HTTP/1.1 415
```

### 6.5. Stripe webhook gia mao bi reject

```bash
curl -k -i -X POST https://localhost:8443/webhooks/stripe \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: t=123,v1=forged" \
  --data-binary @demo/synthetic-data/stripe-payment-succeeded.json
```

Expected:

```text
HTTP/1.1 400
```

## 7. Demo mTLS + ML-DSA tren localhost

Noi voi thay:

> Phan nay demo duong noi bo Kong -> resource-service. Neu khong co client certificate thi fail o TLS handshake. Neu co client certificate nhung thieu ML-DSA assertion thi vao duoc HTTP layer nhung service tra 401. Neu di dung qua Kong thi co ca client cert va ML-DSA assertion nen request hop le tra 200.

### 7.1. Thieu client certificate thi mTLS reject

```bash
docker compose exec -T kong sh -c "printf 'GET /health/live HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -CAfile /etc/kong/certs/internal-ca.crt >/tmp/no-client-cert-local.txt 2>&1 || true; tail -n 30 /tmp/no-client-cert-local.txt"
```

Expected: khong co `HTTP/1.1 200`. Co the thay TLS alert/handshake error.

Noi:

> Case nay fail truoc FastAPI, nen app log co the khong co. Day la dung hanh vi cua mTLS handshake.

### 7.2. Co client cert nhung thieu ML-DSA assertion thi service reject

```bash
docker compose exec -T kong sh -c "printf 'GET /api/v1/resources HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -cert /etc/kong/certs/kong-upstream-client.crt -key /etc/kong/certs/kong-upstream-client.key -CAfile /etc/kong/certs/internal-ca.crt >/tmp/no-mldsa-local.txt 2>&1 || true; head -80 /tmp/no-mldsa-local.txt"
```

Expected:

```text
HTTP/1.1 401
Missing ML-DSA upstream client assertion
```

Noi:

> Day la bang chung ML-DSA duoc rang buoc vao duong upstream. Client cert dung van chua du, request noi bo con phai co ML-DSA assertion.

### 7.3. Di qua Kong thi pass

```bash
curl -k -i https://localhost:8443/api/v1/resources \
  -H "Authorization: Bearer $TOKEN"
```

Expected:

```text
HTTP/1.1 200
```

Noi:

> Kong da inject ML-DSA assertion hop le va dung client certificate khi goi upstream.

### 7.4. Test tron goi mTLS + ML-DSA

Lenh nay co the mat vai phut vi rebuild/recreate container:

```bash
bash scripts/test-tls-plane.sh
```

Expected:

```text
resource-service rejects missing client certificate: ok
resource-service accepts Kong client certificate: ok
resource-service rejects mTLS without ML-DSA assertion: ok
Kong routes with mTLS plus ML-DSA          expected=200 actual=200
Stage 11 TLS plus ML-DSA plane test passed.
```

## 8. Grafana localhost

Mo browser:

```text
http://localhost:3000
```

Login:

```text
username: admin
password: GRAFANA_ADMIN_PASSWORD trong .env
```

Neu dang dung default local:

```text
admin / changeme-grafana
```

Vao:

```text
Explore -> datasource Loki -> Last 15 minutes
```

### 8.1. BOLA log

Sau khi chay `demo/demo-script.sh`, query:

```logql
{event="security.bola_attempt"}
```

Query de doc ro hon:

```logql
{event="security.bola_attempt"} | json | line_format "{{.timestamp}} attacker={{.attacker_tenant_id}} resource_tenant={{.resource_tenant_id}} resource={{.resource_id}} status={{.status_code}}"
```

### 8.2. Webhook gia mao

```logql
{event="security.invalid_webhook_signature"}
```

### 8.3. Request thanh cong qua resource-service

```logql
{service="resource-service", event="api.request", status_code="200"}
```

### 8.4. ML-DSA missing assertion tren kenh mTLS

Tao event truoc:

```bash
docker compose exec -T kong sh -c "printf 'GET /api/v1/resources HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -cert /etc/kong/certs/kong-upstream-client.crt -key /etc/kong/certs/kong-upstream-client.key -CAfile /etc/kong/certs/internal-ca.crt >/tmp/no-mldsa-local.txt 2>&1 || true"
```

Sau do query Grafana:

```logql
{event="internal_mldsa_mtls.missing"}
```

Neu muon loc resource-service:

```logql
{service="resource-service", event="internal_mldsa_mtls.missing"}
```

Noi:

> Log nay chung minh request da qua duoc TLS voi client certificate, nhung service van reject vi khong co ML-DSA assertion.

### 8.5. Kong status logs

```logql
{service="kong"} |= " 401 "
```

```logql
{service="kong"} |= " 403 "
```

```logql
{service="kong"} |= " 415 "
```

```logql
{service="kong"} |= " 429 "
```

## 9. Loi thuong gap khi demo localhost

### Loi `Could not resolve host: keycloak`

Nguyen nhan: terminal host dang dung `KEYCLOAK_URL=http://keycloak:8080`.

Sua bang cach them prefix:

```bash
KEYCLOAK_URL=http://localhost:18080 bash demo/demo-script.sh https://localhost:8443
```

### Smoke test bi `429`

Nguyen nhan: vua chay rate limit demo nen Redis quota con nong.

Sua:

```bash
docker compose exec -T redis redis-cli -a "${REDIS_PASSWORD:-changeme-redis}" FLUSHDB
```

Sau do chay lai smoke test.

### Grafana khong co log

Kiem tra promtail:

```bash
docker compose --profile observability ps promtail
docker compose logs --tail=50 promtail
```

Bat lai:

```bash
docker compose --profile observability up -d promtail
```

### Port 8443 khong dung

Kiem tra port Kong:

```bash
docker compose ps kong
```

Neu `.env` bind `KONG_PROXY_HTTPS_PORT=127.0.0.1:18443`, base URL local la:

```text
https://localhost:18443
```

Khi do chay:

```bash
KEYCLOAK_URL=http://localhost:18080 bash demo/demo-script.sh https://localhost:18443
```

## 10. Thu tu demo de di muot

1. `docker compose ps`
2. `KEYCLOAK_URL=http://localhost:18080 bash scripts/internet-smoke-test.sh https://localhost:8443`
3. `KEYCLOAK_URL=http://localhost:18080 bash demo/demo-script.sh https://localhost:8443`
4. Decode JWT claims.
5. Chay 2 lenh mTLS/ML-DSA negative cases.
6. Mo Grafana:
   - `{event="security.bola_attempt"}`
   - `{event="security.invalid_webhook_signature"}`
   - `{event="internal_mldsa_mtls.missing"}`
   - `{service="resource-service", event="api.request", status_code="200"}`
7. Ket luan:

> Ban localhost chung minh cung mot luong security nhu ban deploy: client vao Gateway, Gateway enforce JWT/OPA/WAF/rate limit, service enforce tenant isolation, upstream noi bo co mTLS va ML-DSA assertion, tat ca co log bang Grafana/Loki.
