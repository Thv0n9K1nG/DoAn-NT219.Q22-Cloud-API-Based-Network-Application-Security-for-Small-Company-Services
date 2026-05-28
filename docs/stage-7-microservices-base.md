# Stage 7 Microservices Base

Stage 7 turns the four service folders into runnable FastAPI applications. The
services intentionally expose only metadata, health, and OpenAPI skeletons; CRUD
and tenant business rules are implemented in later stages.

## Port Convention

All service containers listen on internal port `8000`. Docker DNS separates
them by service name:

| Compose service    | Internal URL                   |
| ------------------ | ------------------------------ |
| `user-service`     | `http://user-service:8000`     |
| `resource-service` | `http://resource-service:8000` |
| `admin-service`    | `http://admin-service:8000`    |
| `payment-service`  | `http://payment-service:8000`  |

This keeps Dockerfiles uniform and lets Kong route by upstream DNS name in later
stages.

## Service Structure

Each service has:

- `app/main.py`
- `app/api/v1/routes.py`
- `app/core/{config,logging,security}.py`
- `app/db/database.py`
- `app/models/schemas.py`
- `app/services/business_logic.py`
- `Dockerfile`
- `tests/test_health.py`
- `tests/test_openapi.py`

## Test Commands

```powershell
pytest services/user-service/tests -v
pytest services/resource-service/tests -v
pytest services/admin-service/tests -v
pytest services/payment-service/tests -v
```

Docker build and runtime smoke test:

```powershell
docker compose build user-service resource-service admin-service payment-service
docker compose up -d postgres vault keycloak user-service resource-service admin-service payment-service
docker compose exec user-service python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health/live').read().decode())"
docker compose exec resource-service python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/openapi.json').read().decode()[:120])"
```
