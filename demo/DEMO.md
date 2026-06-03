# Huong dan demo do an NT219 - ban bao ve cuoi cung

Muc tieu cua demo: chung minh day khong chi la API chay duoc, ma la mot he thong SaaS nho co cac lop bao ve ro rang:

- Public HTTPS entrypoint qua Caddy/Kong.
- Keycloak cap JWT co tenant claims.
- Kong + OPA chan request sai quyen.
- Service va database enforce tenant isolation, chong BOLA.
- WAF-lite, rate limit, webhook verification.
- mTLS noi bo Kong -> service.
- ML-DSA-65 assertion tren kenh mTLS noi bo.
- Loki/Grafana ghi nhan bang chung log.

## 0. Cach noi tong quan voi thay

Noi cham va ro:

> Do an cua em la mot he thong API security cho cong ty nho dang multi-tenant SaaS. Client ngoai Internet chi di vao qua HTTPS public domain. Sau do Gateway kiem tra JWT, goi OPA de quyet dinh authorization, ap dung rate limit va WAF-lite. Ben trong, Kong goi cac microservice qua mTLS. Ngoai mTLS co dien, em bo sung ML-DSA-65 client assertion: service chi chap nhan request noi bo neu Kong co client certificate hop le va token ML-DSA hop le.

Neu thay hoi "ML-DSA nam o dau?":

> ML-DSA nam o tang application identity tren duong Kong -> service va trong S2S/webhook signing. TLS certificate van la X.509/RSA do stack Kong/Uvicorn/OpenSSL mac dinh, nhung request upstream bat buoc co ML-DSA assertion moi duoc service chap nhan.

## 1. Chuan bi truoc khi vao phong demo

Lam tren server/VPS dang deploy public. Khong demo bang localhost neu thay yeu cau Internet that.

### 1.1. Kiem tra file `.env`

```bash
set -a
source .env
set +a
echo "$PUBLIC_DOMAIN"
echo "$GRAFANA_ADMIN_USER"
```

Can co:

```text
PUBLIC_DOMAIN=<domain-that>
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<mat-khau-grafana>
```

Neu dang dung lab default tren may hien tai:

```text
admin / changeme-grafana
```

### 1.2. Bat full stack kem observability

Neu deploy public lan dau:

```bash
bash scripts/bootstrap-internet-demo.sh
```

Neu stack da co san va chi can dam bao Loki/Grafana/Promtail dang chay:

```bash
docker compose --profile observability up -d loki grafana promtail
docker compose ps
```

Can thay cac service chinh healthy/running:

```text
kong
keycloak
opa
user-service
resource-service
admin-service
payment-service
postgres
redis
vault
loki
grafana
promtail
```

### 1.3. Mo cac tab browser truoc

Tab 1: public API domain:

```text
https://$PUBLIC_DOMAIN
```

Tab 2: Grafana qua SSH tunnel. Tren may ca nhan, chay:

```bash
ssh -L 3000:127.0.0.1:3000 <ssh-user>@<vps-ip>
```

Sau do mo browser:

```text
http://localhost:3000
```

Login Grafana:

```text
username: admin
password: lay tu GRAFANA_ADMIN_PASSWORD trong .env
```

Tab 3: terminal SSH vao VPS, dung de chay lenh demo.

### 1.4. Smoke test truoc khi demo

```bash
bash scripts/internet-smoke-test.sh "https://$PUBLIC_DOMAIN"
```

Expected:

```text
gateway rejects missing token                    expected=401 actual=401
tenant user lists resources                      expected=200 actual=200
tenant user denied admin route                   expected=403 actual=403
non-json write rejected                          expected=415 actual=415
forged Stripe webhook rejected                   expected=400 actual=400
Internet smoke test passed.
```

Noi voi thay:

> Day la smoke test tren public domain. Tat ca request deu di qua Internet endpoint, khong phai goi local service.

## 2. Demo luong tong the bang script chinh

Chay:

```bash
bash demo/demo-script.sh "https://$PUBLIC_DOMAIN"
```

Script nay se tao bang chung cho nhieu phan:

- Lay token Keycloak cho alpha user va beta user.
- Request khong token bi Kong reject `401`.
- Alpha tenant list resource duoc `200`.
- Alpha tao resource thanh cong.
- Beta co gang doc resource cua Alpha bi chan `403`.
- Tenant user vao admin route bi OPA/Kong chan `403`.
- Non-JSON write bi WAF-lite chan `415`.
- Goi qua gioi han bi rate limit `429`.
- Stripe webhook gia mao bi reject `400`.
- ML-DSA sign/verify token hop le, token bi sua bi reject.

Khi script chay xong, giu terminal do tren man hinh. Day la bang chung nhanh nhat cho luong tong the.

## 3. Demo tung phan neu thay muon xem rieng

### 3.1. Public API online nhung khong cho request vo danh

```bash
curl -i "https://$PUBLIC_DOMAIN/api/v1/resources"
```

Expected:

```text
HTTP/1.1 401
```

Noi:

> Request tu Internet vao domain that. Gateway reject vi thieu JWT, request khong duoc vao service nghiep vu.

### 3.2. Lay JWT tu Keycloak va show tenant claims

```bash
TOKEN="$(bash scripts/get-token.sh alpha-user@example.com "${KEYCLOAK_LAB_USER_PASSWORD:-TestPass123!}")"
export TOKEN
python - <<'PY'
import base64, json, os
token = os.environ["TOKEN"]
payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)
claims = json.loads(base64.urlsafe_b64decode(payload))
print(json.dumps({
    "sub": claims.get("sub"),
    "tenant_id": claims.get("tenant_id"),
    "aud": claims.get("aud"),
    "roles": claims.get("realm_access", {}).get("roles", []),
    "exp": claims.get("exp"),
    "jti": claims.get("jti"),
}, indent=2))
PY
```

Can chi ra:

- `tenant_id`: service dung de enforce tenant isolation.
- `aud`: phai la `saas-api`.
- `roles`: dung cho RBAC/OPA.
- `exp`, `jti`: phuc vu token lifecycle/replay reasoning.

### 3.3. Tenant Alpha doc resource cua minh

```bash
curl -k -s "https://$PUBLIC_DOMAIN/api/v1/resources" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool
```

Expected: JSON list resource cua tenant Alpha.

Noi:

> Service lay tenant tu JWT da verify, khong tin tenant_id do client tu gui.

### 3.4. BOLA/cross-tenant attack bi chan

Dung script chinh la cach nhanh nhat:

```bash
bash demo/demo-script.sh "https://$PUBLIC_DOMAIN"
```

Chi vao dong:

```text
beta GET alpha resource -> 403
```

Noi:

> Beta user co token hop le, nhung khong thuoc tenant Alpha. Service van reject. Day la BOLA protection.

### 3.5. OPA/Gateway authorization

Trong output script, chi vao:

```text
alpha user GET admin tenants -> 403
```

Noi:

> Request co JWT hop le nhung role khong du, OPA policy khong cho vao admin API.

### 3.6. WAF-lite content-type enforcement

Trong output script, chi vao:

```text
POST without application/json -> 415
```

Noi:

> Gateway yeu cau write request phai la JSON dung content type, giam request bat thuong truoc khi vao service.

### 3.7. Rate limiting theo tenant

Trong output script, phan rate limit se co dang:

```text
20 200
5 429
```

Noi:

> Kong rate limit theo header tenant da duoc OPA plugin ghi de tu JWT da verify. Client khong the tu doi tenant header de ne quota.

### 3.8. Stripe webhook forgery bi reject

```bash
curl -i "https://$PUBLIC_DOMAIN/webhooks/stripe" \
  -H "Content-Type: application/json" \
  -H "Stripe-Signature: t=123,v1=forged" \
  --data-binary @demo/synthetic-data/stripe-payment-succeeded.json
```

Expected:

```text
HTTP/1.1 400
```

Noi:

> Inbound Stripe webhook dung Stripe signature/HMAC vi Stripe la ben gui. ML-DSA cua do an dung cho S2S token va outbound/application-layer signing cua he thong.

## 4. Demo mTLS + ML-DSA upstream

Day la phan quan trong neu thay bat buoc co ML-DSA gan voi mTLS.

### 4.1. Cau noi truoc khi chay

Noi:

> Em demo rieng duong noi bo Kong -> resource-service. Co 3 truong hop: khong co client certificate thi fail tai TLS handshake; co client certificate nhung thieu ML-DSA assertion thi service tra 401; di dung qua Kong thi co ca mTLS va ML-DSA assertion nen service tra 200.

### 4.2. Chung minh thieu client certificate thi mTLS reject

Chay:

```bash
docker compose exec -T kong sh -c "printf 'GET /health/live HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -CAfile /etc/kong/certs/internal-ca.crt >/tmp/no-client-cert-demo.txt 2>&1 || true; tail -n 30 /tmp/no-client-cert-demo.txt"
```

Expected: khong co `HTTP/1.1 200`. Thuong se thay TLS alert/handshake error.

Noi:

> Request nay khong co client cert nen bi chan truoc khi vao FastAPI. Vi fail o TLS handshake nen co the khong co application log trong Grafana. Bang chung phan nay la ket qua openssl va cau hinh Uvicorn `--ssl-cert-reqs 2`.

### 4.3. Chung minh co client cert nhung thieu ML-DSA van fail

Chay:

```bash
docker compose exec -T kong sh -c "printf 'GET /api/v1/resources HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -cert /etc/kong/certs/kong-upstream-client.crt -key /etc/kong/certs/kong-upstream-client.key -CAfile /etc/kong/certs/internal-ca.crt >/tmp/no-mldsa-demo.txt 2>&1 || true; head -80 /tmp/no-mldsa-demo.txt"
```

Expected co:

```text
HTTP/1.1 401
Missing ML-DSA upstream client assertion
```

Noi:

> Day la diem ML-DSA. Ket noi da co client certificate cua Kong, nhung service van reject vi thieu `X-Internal-MLDSA-Token` hop le.

### 4.4. Chung minh di qua Kong thi pass

```bash
curl -k -i "https://$PUBLIC_DOMAIN/api/v1/resources" \
  -H "Authorization: Bearer $TOKEN"
```

Expected:

```text
HTTP/1.1 200
```

Noi:

> Khi request di dung public Gateway, Kong verify JWT/OPA, sau do goi upstream bang client certificate va tu inject ML-DSA assertion. Service verify thanh cong nen tra 200.

### 4.5. Neu can chay test tron goi

Lenh nay mat vai phut vi co the rebuild/recreate service:

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

Noi:

> Test nay gom ca positive va negative cases cho TLS/mTLS/ML-DSA.

## 5. Huong dan Grafana/Loki tren browser

### 5.1. Dam bao Promtail dang day log vao Loki

Tren VPS:

```bash
docker compose --profile observability up -d loki grafana promtail
docker compose ps loki grafana promtail
```

Expected:

```text
loki      healthy/running
grafana   healthy/running
promtail  running
```

### 5.2. Mo Grafana

Neu Grafana khong public, dung SSH tunnel:

```bash
ssh -L 3000:127.0.0.1:3000 <ssh-user>@<vps-ip>
```

Mo browser:

```text
http://localhost:3000
```

Login:

```text
username: admin
password: GRAFANA_ADMIN_PASSWORD trong .env
```

### 5.3. Vao Explore

Trong Grafana:

1. Bam menu ben trai.
2. Chon `Explore`.
3. Data source chon `Loki`.
4. Time range chon `Last 15 minutes`.
5. Paste query.
6. Bam `Run query`.
7. Bam vao log line de expand JSON fields.

### 5.4. Query log BOLA

Sau khi chay `demo/demo-script.sh`, paste:

```logql
{event="security.bola_attempt"}
```

Neu muon hien dong de doc nhanh:

```logql
{event="security.bola_attempt"} | json | line_format "{{.timestamp}} attacker={{.attacker_tenant_id}} resource_tenant={{.resource_tenant_id}} resource={{.resource_id}} status={{.status_code}}"
```

Noi:

> Log nay chung minh service phat hien cross-tenant read va ghi lai bang chung security event.

### 5.5. Query log webhook gia mao

Sau khi chay forged Stripe webhook:

```logql
{event="security.invalid_webhook_signature"}
```

Noi:

> Log nay chung minh webhook gia mao khong duoc xu ly am tham, ma bi reject va co audit trail.

### 5.6. Query log request thanh cong qua resource-service

Sau khi call:

```bash
curl -k -i "https://$PUBLIC_DOMAIN/api/v1/resources" -H "Authorization: Bearer $TOKEN"
```

Trong Grafana Explore:

```logql
{service="resource-service", event="api.request", status_code="200"}
```

Noi:

> Day la log request da vao resource-service thanh cong sau khi di qua Gateway. Ket hop voi negative test ML-DSA o buoc tiep theo, em chung minh request hop le qua Kong duoc pass, request mTLS thieu ML-DSA bi reject.

### 5.7. Query log ML-DSA assertion thieu tren kenh mTLS

Truoc tien tao event bang lenh:

```bash
docker compose exec -T kong sh -c "printf 'GET /api/v1/resources HTTP/1.1\r\nHost: resource-service\r\n\r\n' | openssl s_client -quiet -connect resource-service:8000 -servername resource-service -cert /etc/kong/certs/kong-upstream-client.crt -key /etc/kong/certs/kong-upstream-client.key -CAfile /etc/kong/certs/internal-ca.crt >/tmp/no-mldsa-demo.txt 2>&1 || true"
```

Sau do vao Grafana Explore, query:

```logql
{event="internal_mldsa_mtls.missing"}
```

Neu muon loc rieng resource-service:

```logql
{service="resource-service", event="internal_mldsa_mtls.missing"}
```

Noi:

> Log nay phan anh lop ML-DSA tren kenh mTLS. Request da dung client certificate nhung khong co ML-DSA assertion, nen service ghi event `internal_mldsa_mtls.missing` va tra 401.

### 5.8. Giai thich ve log mTLS thieu client certificate

Neu thay hoi vi sao case "missing client certificate" khong thay log app ro nhu ML-DSA:

> Case thieu client certificate fail o TLS handshake truoc khi HTTP request vao FastAPI, nen app middleware khong co co hoi ghi log JSON. Vi vay bang chung cua case do la openssl output/script output. Con Grafana ghi duoc case ML-DSA missing vi request da qua TLS voi client cert, vao duoc HTTP layer, roi bi middleware ML-DSA reject.

Neu muon tim raw log lien quan TLS trong Grafana, co the thu:

```logql
{service="resource-service"} |= "TLS"
```

hoac:

```logql
{service="resource-service"} |= "certificate"
```

Nhung khong nen phu thuoc vao hai query nay khi bao ve, vi TLS handshake error co the nam o stderr format khac nhau tuy image/runtime.

### 5.9. Query Kong raw logs cho status 401/403/415/429

Trong Grafana Explore:

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

Noi:

> Day la log tu Gateway, cho thay security controls duoc enforce o entrypoint.

## 6. Dashboards nen mo neu co thoi gian

Trong Grafana, vao `Dashboards`:

- `NT219 API Traffic`: request/status tong quan.
- `NT219 Security Events`: auth failure, BOLA, webhook failure, rate limit.
- `NT219 Tenant Activity`: hoat dong theo tenant.

Neu dashboard khong co data ngay, quay lai `Explore` va dung cac query LogQL o muc 5 vi do la cach chac chan nhat.

## 7. Cau tra loi nhanh khi bi hoi kho

### "mTLS nay co phai ML-DSA certificate khong?"

Tra loi:

> Khong. TLS certificate hien tai la X.509/RSA do Kong/Uvicorn/OpenSSL mac dinh. Diem em bo sung la ML-DSA-65 client assertion bat buoc tren kenh mTLS. Nghia la service khong chi kiem tra client cert, ma con verify token ML-DSA cua Kong. Day la demo-grade PQC identity binding cho upstream mTLS.

### "Neu client ngoai Internet tu gui X-Internal-MLDSA-Token thi sao?"

Tra loi:

> Kong cau hinh request-transformer de xoa header `X-Internal-MLDSA-Token` tu client ngoai, sau do Kong moi them token ML-DSA cua no. Vi vay client ngoai khong the spoof assertion nay qua gateway.

Co the chi file:

```bash
grep -n "X-Internal-MLDSA-Token" gateway/kong.template.yml
```

### "Service co private key ML-DSA khong?"

Tra loi:

> Khong. Service chi co public key de verify. Private key/token ML-DSA nam phia Kong trong `gateway/certs`. Service verify duoc nhung khong tu tao assertion hop le duoc.

### "Vi sao dung OPA neu service van check tenant?"

Tra loi:

> OPA/Gateway la enforcement som o entrypoint. Service/database van enforce lai de co defense-in-depth. Neu gateway config sai, service va RLS van bao ve tenant isolation.

### "Day da production chua?"

Tra loi:

> Day la prototype demo cho mon hoc, co public HTTPS va security controls co the test duoc. De production can thay Vault dev mode, harden secrets, HA deployment, real cert lifecycle, CI/CD va monitoring canh bao day du hon.

## 8. Thu tu demo de thuyet phuc nhat trong 10-15 phut

1. Mo public domain va noi kien truc tong quan.
2. Chay `bash scripts/internet-smoke-test.sh "https://$PUBLIC_DOMAIN"`.
3. Chay `bash demo/demo-script.sh "https://$PUBLIC_DOMAIN"`.
4. Show token claims bang Python decode.
5. Chi output BOLA `403`, admin `403`, WAF `415`, rate limit `429`, webhook `400`.
6. Chay case mTLS thieu client cert bang openssl.
7. Chay case co client cert nhung thieu ML-DSA assertion, thay `401`.
8. Vao Grafana Explore:
   - `{event="security.bola_attempt"}`
   - `{event="security.invalid_webhook_signature"}`
   - `{event="internal_mldsa_mtls.missing"}`
   - `{service="resource-service", event="api.request", status_code="200"}`
9. Ket luan bang cau:

> He thong cua em co public API, Gateway security, identity provider, authorization policy, tenant isolation, attack detection, mTLS noi bo, ML-DSA upstream assertion va observability de chung minh cac control da hoat dong.

## 9. Checklist cuoi truoc khi bao ve

Chay nhanh:

```bash
docker compose --profile observability ps
python -m pytest -q
bash scripts/internet-smoke-test.sh "https://$PUBLIC_DOMAIN"
```

Neu co thoi gian va muon test lai mTLS + ML-DSA full:

```bash
bash scripts/test-tls-plane.sh
```

Mo Grafana va dam bao query nay co data:

```logql
{event="api.request"}
```

Sau do chay demo-script va dam bao co:

```logql
{event="security.bola_attempt"}
{event="security.invalid_webhook_signature"}
```

Tao ML-DSA missing event va dam bao co:

```logql
{event="internal_mldsa_mtls.missing"}
```
