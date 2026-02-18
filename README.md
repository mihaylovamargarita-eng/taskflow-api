# TaskFlow API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.13%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)

Modern task management REST API built with FastAPI, PostgreSQL, SQLAlchemy, and JWT authentication.

## Live Demo

- Swagger UI: https://api.dtodorov.dev/docs

## Features

- JWT-based authentication with refresh token rotation and reuse detection
- RBAC with `user` and `admin` roles
- Secure password hashing with bcrypt
- Task CRUD endpoints scoped to authenticated users
- Filtering and pagination for task listing
- SQLAlchemy ORM models with typed enums and timestamps
- Alembic migrations for versioned schema management
- Pydantic validation for request/response schemas
- Environment-based configuration
- Dockerized API + PostgreSQL setup
- Health endpoints for liveness/readiness probes
- Request logging with `X-Request-ID` correlation
- Prometheus metrics endpoint for monitoring
- Configurable rate limiting policies for auth/read/write APIs
- Security headers middleware for baseline HTTP hardening
- CI pipeline with lint, unit/integration tests, migration gate, and E2E stage

## Tech Stack

- Python 3.13+
- FastAPI
- SQLAlchemy 2.x
- PostgreSQL 15
- Pydantic v2
- PyJWT (JWT)
- passlib (bcrypt)
- Docker & Docker Compose

## Local Setup

1. Clone the repository:

```bash
git clone <your-repo-url>
cd taskflow-api
```

2. Copy environment template:

```bash
cp .env.example .env
```

3. Install dependencies (optional if running only via Docker):

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

4. Run with Docker Compose:

```bash
docker compose up --build
```

5. Access the API docs:

- http://localhost:${APP_PORT:-8010}/docs

Note:
- In Docker Compose, migrations run automatically on API startup (`alembic upgrade head`).
- For local runs outside Docker, run migrations manually before starting the API.

## Quality Checks

Run quality checks locally:

```bash
ruff check app tests
python -m compileall app alembic
pytest -q -m "not e2e"
```

These checks are also executed in CI (`.github/workflows/ci.yml`).

## Contract Tests

OpenAPI contract tests verify schema integrity and backward compatibility:

```bash
pytest -q tests/test_openapi_contract.py
```

These checks enforce:
- required endpoint path/method presence
- required schema fields for key response models
- standardized `ErrorResponse` references on protected/error-prone endpoints
- compatibility against `tests/contracts/openapi_backward_compat.json`

## E2E Tests

Run end-to-end tests against a running API instance.

1. Start the stack:
```bash
docker compose up --build
```

2. In another terminal, run E2E tests:
```bash
docker compose exec api sh -lc "E2E_BASE_URL=http://localhost:8000 pytest -q -m e2e tests/e2e"
```

Notes:
- E2E tests hit real HTTP endpoints and database-backed flows.
- They cover auth lifecycle (including refresh rotation/reuse/logout), task lifecycle, filters, pagination, and ownership boundaries.

## API Endpoints Overview

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| POST | `/api/auth/register` | Register a new user | No |
| POST | `/api/auth/login` | Login and receive access + refresh tokens | No |
| POST | `/api/auth/refresh` | Rotate refresh token and issue new token pair | No (refresh token required) |
| POST | `/api/auth/logout` | Revoke active refresh sessions for current user | Yes |
| GET | `/api/auth/me` | Get current authenticated user | Yes |
| GET | `/api/tasks` | List current user tasks (filters + pagination) | Yes |
| POST | `/api/tasks` | Create a task | Yes |
| GET | `/api/tasks/{task_id}` | Get a single task by ID | Yes |
| PUT | `/api/tasks/{task_id}` | Update task fields | Yes |
| DELETE | `/api/tasks/{task_id}` | Delete a task | Yes |
| GET | `/api/health/live` | Liveness probe endpoint | No |
| GET | `/api/health/ready` | Readiness probe with DB check | No |
| GET | `/api/metrics` | Prometheus-compatible metrics | No |
| GET | `/api/admin/users` | List users (admin) | Yes (Admin) |
| PATCH | `/api/admin/users/{user_id}/role` | Update user role (admin) | Yes (Admin) |
| PATCH | `/api/admin/users/{user_id}/status` | Activate/deactivate user (admin) | Yes (Admin) |
| GET | `/api/admin/stats` | Platform stats (admin) | Yes (Admin) |

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | - | SQLAlchemy connection URL used by the API |
| `JWT_SECRET` | Yes | - | Secret key used to sign JWT tokens |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token expiration time |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | No | `10080` | Refresh token expiration time |
| `AUTO_CREATE_TABLES` | No | `false` | Enable `create_all` on startup (development only) |
| `ENVIRONMENT` | No | `development` | Runtime environment profile (`development/staging/production`) |
| `LOG_FORMAT` | No | `json` | Log format (`json` or `plain`) |
| `CORS_ALLOW_ORIGINS` | No | `*` | Comma-separated CORS origins |
| `CORS_ALLOW_CREDENTIALS` | No | `true` | Whether to allow credentialed CORS requests |
| `CORS_ALLOW_METHODS` | No | `*` | Comma-separated CORS methods |
| `CORS_ALLOW_HEADERS` | No | `*` | Comma-separated CORS headers |
| `ENABLE_SECURITY_HEADERS` | No | `true` | Enable security response headers middleware |
| `ENABLE_HSTS` | No | `false` | Enable `Strict-Transport-Security` header |
| `RATE_LIMIT_DEFAULT` | No | `120/minute` | Default limiter policy for all endpoints |
| `RATE_LIMIT_AUTH` | No | `20/minute` | Limiter policy for auth endpoints |
| `RATE_LIMIT_WRITE` | No | `60/minute` | Limiter policy for write endpoints |
| `RATE_LIMIT_READ` | No | `240/minute` | Limiter policy for read endpoints |
| `BOOTSTRAP_ADMIN_ENABLED` | No | `false` | Enable startup bootstrap for initial admin account |
| `BOOTSTRAP_ADMIN_EMAIL` | No | - | Email for bootstrap admin account |
| `BOOTSTRAP_ADMIN_PASSWORD` | No | - | Password for bootstrap admin account (min 8 chars) |
| `POSTGRES_DB` | Docker | `taskflow` | PostgreSQL database name (Compose) |
| `POSTGRES_USER` | Docker | `postgres` | PostgreSQL user (Compose) |
| `POSTGRES_PASSWORD` | Docker | `postgres` | PostgreSQL password (Compose) |

Notes:
- For Docker Compose, set `DATABASE_URL` to point to the `db` service host, for example:  
  `postgresql+psycopg://postgres:postgres@db:5432/taskflow`
- Use a strong `JWT_SECRET` in production.
- Keep `AUTO_CREATE_TABLES=false` in production and run Alembic migrations instead.
- For demo environments, you can enable bootstrap admin provisioning to avoid manual DB role setup.
- `TASK_MAX_PER_USER` is currently enforced at the application layer (domain policy), not by a database constraint.
- For strict hard caps under concurrent writes, add DB-level enforcement in a future migration strategy.

Example demo bootstrap config:
```env
BOOTSTRAP_ADMIN_ENABLED=true
BOOTSTRAP_ADMIN_EMAIL=admin@demo.local
BOOTSTRAP_ADMIN_PASSWORD=ChangeMe123!
```

## Database Migrations

Use Alembic for all schema changes:

```bash
# apply latest migrations
alembic upgrade head

# rollback one revision
alembic downgrade -1

# create a new revision
alembic revision -m "describe change"
```

For local development without Docker:
```bash
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Deployment Notes

- Use a production-grade reverse proxy (Nginx, Traefik, or cloud load balancer) in front of Uvicorn.
- Terminate TLS at the proxy/load balancer and enforce HTTPS.
- Do not expose PostgreSQL publicly; keep it on a private network.
- Replace default credentials and secrets with secure values.
- Use short-lived access tokens and rotate refresh tokens on every refresh request.
- Keep refresh token data in the database and revoke sessions on logout or reuse detection.
- For demos and local Compose, auto-running migrations on startup is enabled.
- For production, run migrations as a separate deployment step/job before starting new app instances.
- Enable strict CORS origins in non-demo environments.
- Keep authentication rate limits strict and tuned to expected traffic.
- Expose `/api/metrics` to Prometheus (prefer private network scraping).
- Configure monitoring, centralized logs, and health checks for operational visibility.
- Ship request logs to centralized observability tooling and preserve `X-Request-ID` across services.

## Architecture Notes

- Router layer: HTTP endpoints and request handling (`app/routers`).
- Schema layer: API contracts and validation (`app/schemas.py`).
- Model layer: SQLAlchemy entities and relationships (`app/models.py`).
- Auth layer: password hashing and token lifecycle management (`app/auth.py`).
- Infrastructure layer: database sessions, Alembic, Docker, and CI.
- Detailed rationale: `docs/architecture-decisions.md`.

## License

This project is licensed under the MIT License.
