# Kich ban demo truc tiep cho thay

File nay da duoc rut gon de tranh nham voi ban cu.

Dung file demo moi sau:

```text
docs/mldsa-mtls-live-demo.md
```

Noi dung cap nhat hien tai:

- Upstream Kong -> service dung mTLS co dien de xac thuc kenh TLS.
- Tren duong mTLS do, Kong bat buoc gan ML-DSA-65 client assertion.
- Service verify token ML-DSA bang public key.
- Neu co client certificate nhung thieu ML-DSA assertion, service tra `401`.
- Smoke test da pass voi lenh:

```bash
bash scripts/test-tls-plane.sh
```

Output quan trong:

```text
resource-service rejects missing client certificate: ok
resource-service accepts Kong client certificate: ok
resource-service rejects mTLS without ML-DSA assertion: ok
Kong routes with mTLS plus ML-DSA          expected=200 actual=200
Stage 11 TLS plus ML-DSA plane test passed.
```

Mo file `docs/mldsa-mtls-live-demo.md` de doc kich ban day du khi bao ve.
