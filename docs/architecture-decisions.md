# Architecture Decisions

## 1. FastAPI + SQLAlchemy + Pydantic

- FastAPI provides type-driven API development and OpenAPI docs.
- SQLAlchemy ORM gives explicit relational modeling and migration compatibility.
- Pydantic v2 enforces strict request/response contracts.

## 2. JWT Access + Refresh Rotation

- Access tokens are short-lived and stateless.
- Refresh tokens are persisted server-side and rotated at each refresh.
- Reuse detection revokes active sessions to reduce token theft impact.

## 3. Migration-First Database Changes

- Alembic is the source of truth for schema evolution.
- Docker Compose auto-runs migrations for demo convenience.
- Production guidance remains explicit migrations as a controlled deployment step.

## 4. Operational Readiness

- Health endpoints support container orchestration probes.
- Request logging includes correlation via `X-Request-ID`.
- CI enforces linting and test execution on pull requests.

