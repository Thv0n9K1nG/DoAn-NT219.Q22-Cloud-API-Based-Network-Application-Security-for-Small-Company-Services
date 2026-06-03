# Kich ban demo: mTLS co ML-DSA bat buoc tren duong Kong -> Service

## 1. Cau noi mo dau voi thay

> Do an cua em dung Kong lam API Gateway. Duong ben ngoai vao Kong dung HTTPS va JWT/OPA. Rieng duong noi bo tu Kong vao cac microservice duoc bao ve bang hai lop: mTLS X.509 de xac thuc kenh TLS, va ML-DSA-65 de xac thuc danh tinh upstream client o tang ung dung. Neu chi co client certificate ma thieu ML-DSA assertion thi service se tu choi request.

Noi ngan gon:

- mTLS: bat buoc Kong trinh client certificate khi goi service.
- ML-DSA: Kong phai gan token `X-Internal-MLDSA-Token` da ky bang ML-DSA-65.
- Service: verify public key ML-DSA, sai/thieu token thi tra `401`.

## 2. Vi tri code can chi cho thay

ML-DSA core:

```bash
shared/pqc_signing.py
shared/s2s_token.py
shared/internal_mldsa_mtls.py
```

Kong inject ML-DSA assertion:

```bash
gateway/kong.template.yml
scripts/kong-init.sh
```

Sinh key/token ML-DSA demo:

```bash
scripts/generate-dev-certs.sh
```

Docker bat enforcement cho 4 service:

```bash
docker-compose.yml
```

Test chung:

```bash
scripts/test-tls-plane.sh
tests/test_internal_mldsa_mtls.py
tests/test_gateway_config.py
```

## 3. Lenh demo nhanh nhat

Chay lenh nay de demo tron goi:

```bash
bash scripts/test-tls-plane.sh
```

Ket qua quan trong can chi ra:

```text
resource-service rejects missing client certificate: ok
resource-service accepts Kong client certificate: ok
resource-service rejects mTLS without ML-DSA assertion: ok
Kong routes with mTLS plus ML-DSA          expected=200 actual=200
Stage 11 TLS plus ML-DSA plane test passed.
```

Cach giai thich:

> Dong thu nhat chung minh service khong chap nhan request khong co client cert. Dong thu ba moi la phan ML-DSA: request da co client cert nhung khong co ML-DSA assertion van bi chan. Dong cuoi cung chung minh request di qua Kong thanh cong vi Kong co ca client cert va ML-DSA assertion.

## 4. Demo bang cac buoc rieng

### Buoc 1: Kiem tra container dang chay

```bash
docker compose ps
```

Can thay cac service chinh dang `running`/`healthy`:

```text
kong
keycloak
resource-service
user-service
admin-service
payment-service
postgres
redis
opa
```

### Buoc 2: Chung minh co key/token ML-DSA

```bash
ls gateway/certs/mldsa-upstream-client.*
```

Expected:

```text
gateway/certs/mldsa-upstream-client.key
gateway/certs/mldsa-upstream-client.pub
gateway/certs/mldsa-upstream-client.token
```

Noi voi thay:

> Private key va token ML-DSA nam phia Kong. Public key duoc copy sang tung service de verify. Service khong can biet private key.

### Buoc 3: Chung minh service co public key de verify

```bash
ls services/resource-service/certs/mldsa-upstream-client.pub
```

Noi voi thay:

> Day la public key ML-DSA ma resource-service dung de verify token do Kong gui len.

### Buoc 4: Chung minh Kong inject header ML-DSA

```bash
grep -n "X-Internal-MLDSA-Token" gateway/kong.yml
```

Expected co cac dong:

```text
remove:
  headers:
    - X-Internal-MLDSA-Token
add:
  headers:
    - X-Internal-MLDSA-Token:...
```

Noi voi thay:

> Kong xoa header ML-DSA neu client ben ngoai co tinh gia mao, sau do Kong tu gan token ML-DSA that cua gateway vao request noi bo.

### Buoc 5: Chung minh thieu client cert thi fail

Lenh nay da nam trong smoke test, neu muon chay tron goi:

```bash
bash scripts/test-tls-plane.sh
```

Can chi vao dong:

```text
resource-service rejects missing client certificate: ok
```

Noi voi thay:

> Day la lop mTLS. Service yeu cau client certificate khi nhan ket noi TLS noi bo.

### Buoc 6: Chung minh co client cert nhung thieu ML-DSA van fail

Trong output cua smoke test, chi vao dong:

```text
resource-service rejects mTLS without ML-DSA assertion: ok
```

Noi voi thay:

> Day la diem em bo sung ML-DSA vao mTLS demo. Request nay da dung client cert cua Kong, nhung vi khong co token ML-DSA nen service van reject.

### Buoc 7: Chung minh di qua Kong thi pass

Trong output cua smoke test, chi vao dong:

```text
Kong routes with mTLS plus ML-DSA          expected=200 actual=200
```

Noi voi thay:

> Khi request di dung duong qua Kong, Kong co client certificate hop le va gan ML-DSA assertion hop le, nen service chap nhan va tra 200.

## 5. Test unit de chung minh ML-DSA verify that

Chay:

```bash
python -m pytest -q tests/test_internal_mldsa_mtls.py tests/test_gateway_config.py
```

Expected:

```text
6 passed
```

Noi voi thay:

> Unit test tao keypair ML-DSA that, ky token that, middleware verify bang public key that. Day khong phai string mock.

## 6. Test toan bo codebase

Chay:

```bash
python -m pytest -q
```

Expected hien tai:

```text
84 passed
```

## 7. Cau tra loi neu thay hoi "co phai TLS certificate la ML-DSA khong?"

Tra loi nhu sau:

> Trong ban demo nay, certificate TLS van la X.509/RSA vi Kong, Uvicorn va OpenSSL mac dinh chua ho tro ML-DSA certificate native mot cach on dinh. Tuy nhien duong mTLS noi bo da duoc rang buoc them bang ML-DSA-65: service khong chi kiem tra client certificate ma con bat buoc request tu Kong phai co ML-DSA assertion hop le. Vi vay day la mo hinh mTLS co xac thuc hau luong tu o tang ung dung, phu hop de demo trong mon hoc.

Neu can noi ngan hon:

> TLS channel dung mTLS co dien, con client identity cua Kong tren channel do duoc ky va verify bang ML-DSA-65.

## 8. Cau tra loi neu thay hoi "neu hacker tu them header ML-DSA thi sao?"

Tra loi:

> Kong cau hinh `request-transformer` de xoa `X-Internal-MLDSA-Token` tu request ben ngoai truoc, sau do moi them token ML-DSA cua Kong. Vi vay client ben ngoai khong the spoof header nay qua gateway.

Chi vao:

```bash
grep -n "X-Internal-MLDSA-Token" gateway/kong.template.yml
```

## 9. Cau tra loi neu thay hoi "vi sao token khong bi service nao cung tao duoc?"

Tra loi:

> Service chi co public key de verify. Private key ML-DSA nam phia Kong trong `gateway/certs/mldsa-upstream-client.key` va khong copy sang service. Nen service verify duoc, nhung khong tu tao token hop le duoc.

## 10. Thu tu demo khuyen nghi trong luc bao ve

1. Mo kien truc va noi: Gateway, IdP, OPA, service, database.
2. Chay `docker compose ps` de cho thay he thong dang song.
3. Chay `bash scripts/test-tls-plane.sh`.
4. Chi vao 4 dong output quan trong:
   - reject missing client certificate
   - accept Kong client certificate
   - reject mTLS without ML-DSA assertion
   - Kong routes with mTLS plus ML-DSA expected 200
5. Mo `shared/internal_mldsa_mtls.py` de chi middleware verify.
6. Mo `gateway/kong.template.yml` de chi Kong remove spoofed header va inject token.
7. Chay `python -m pytest -q tests/test_internal_mldsa_mtls.py tests/test_gateway_config.py`.
8. Ket luan: he thong co API Gateway, JWT, OPA, tenant isolation, rate limit, WAF co ban, TLS/mTLS, va ML-DSA tren duong upstream.

## 11. Cau ket luan nen noi

> Diem chinh cua do an la em khong chi lam API chay duoc, ma co security controls co the test duoc: JWT/OPA cho authorization, tenant isolation chong BOLA, rate limiting, webhook verification, observability, mTLS noi bo, va ML-DSA-65 de xac thuc request noi bo tu gateway vao service.
