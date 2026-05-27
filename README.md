# CRA Backend

Copilot Readiness Assessment (CRA) backend for Microsoft 365 readiness, assessment runtime orchestration, PowerShell collector execution, scoring, recommendations, and enterprise report generation.

## Current Capabilities

- FastAPI async API with versioned `/api/v1` routes
- Microsoft Entra ID login using Microsoft ID tokens
- CRA internal JWT access and refresh tokens
- Tenant-scoped protected APIs
- PostgreSQL-ready async SQLAlchemy with SQLite local development support
- Alembic migrations
- Registry-driven assessment parameters, collectors, rules, and recommendations
- Celery assessment runtime with Redis broker/result backend
- Redis pub/sub event fanout
- WebSocket runtime event streaming
- Phase 7B PowerShell collector execution engine
- Runtime scoring and recommendation persistence
- Phase 8A PDF/DOCX CRA report generation

## Architecture

```text
React frontend
    -> FastAPI API
    -> CRA JWT auth
    -> tenant-scoped assessment APIs
    -> Celery assessment job
    -> PowerShellExecutionEngine
    -> collector JSON contract
    -> findings
    -> scoring
    -> recommendations
    -> report generation
    -> PDF/DOCX artifacts

Redis supports Celery and WebSocket event fanout.
```

## Project Structure

```text
app/
├── api/v1/                     # API routers
├── config/assessment_registry/ # parameters, collectors, rules, recommendations
├── core/                       # settings, auth, security, Microsoft token helpers
├── db/models/                  # SQLAlchemy models
├── powershell/                 # PowerShell collector scripts
├── schemas/                    # Pydantic response/request schemas
├── services/
│   ├── powershell/             # Phase 7B PowerShell runtime engine
│   ├── reporting/              # Phase 8A report engine
│   └── simulated_collectors/   # legacy/test collector helpers
└── tasks/                      # Celery task entry points

migrations/                     # Alembic migrations
tests/                          # pytest validation suite
storage/reports/                # generated reports, ignored by git
```

## Requirements

- Python 3.11+
- Redis 5+
- PowerShell 7+ (`pwsh`) for real collector execution
- PostgreSQL for production, SQLite for local development

Install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy the example environment:

```bash
cp .env.example .env
```

Update `.env` with a real `SECRET_KEY`, Microsoft Entra app registration values, database URL, and Redis URL.

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `APP_NAME` | No | Application display name |
| `APP_VERSION` | No | Application version |
| `DEBUG` | No | Enables development behavior |
| `API_V1_PREFIX` | No | API prefix, default `/api/v1` |
| `CORS_ORIGINS` | No | Comma-separated frontend origins |
| `DATABASE_URL` | Yes | SQLAlchemy database URL |
| `REDIS_URL` | Yes | Redis URL for pub/sub and default Celery broker/backend |
| `CELERY_BROKER_URL` | No | Overrides `REDIS_URL` for Celery broker |
| `CELERY_RESULT_BACKEND` | No | Overrides `REDIS_URL` for Celery result backend |
| `SECRET_KEY` | Yes | CRA JWT signing key |
| `ALGORITHM` | No | JWT algorithm, default `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | Access token TTL |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Refresh token TTL |
| `AZURE_CLIENT_ID` | Yes | Microsoft Entra app client ID |
| `AZURE_TENANT_ID` | Yes | Tenant ID, `common`, or `organizations` |
| `AZURE_CLIENT_SECRET` | Optional | Server-side Microsoft Graph preparation |
| `ORGANIZATION_NAME` | No | Default customer/report organization name |

## Run Locally

Start Redis:

```bash
redis-server
```

Run database migrations:

```bash
alembic upgrade head
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Start Celery worker:

```bash
celery -A app.core.celery_app.celery_app worker --loglevel=info
```

Optional Flower dashboard:

```bash
celery -A app.core.celery_app.celery_app flower
```

## Authentication Flow

This platform does not use email/password registration.

```text
MSAL React -> Microsoft login -> Microsoft ID token
    -> POST /api/v1/auth/login
    -> backend validates Entra token
    -> backend creates/updates user and session
    -> backend returns CRA JWT access_token and refresh_token
    -> frontend uses CRA Bearer token for protected APIs
```

Protected API example:

```bash
curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer <CRA_ACCESS_TOKEN>"
```

## Main API Areas

| Area | Endpoints |
| --- | --- |
| Auth | `/api/v1/auth/login`, `/api/v1/auth/refresh`, `/api/v1/auth/logout`, `/api/v1/auth/me` |
| Assessments | `/api/v1/assessments`, `/api/v1/assessments/{id}` |
| Runtime | `/api/v1/assessments/{id}/events`, `/api/v1/assessments/{id}/job` |
| Findings | `/api/v1/assessments/{id}/findings` |
| Recommendations | `/api/v1/assessments/{id}/recommendations` |
| Reports | `/api/v1/assessments/{id}/generate-report`, `/api/v1/assessments/{id}/report`, `/api/v1/assessments/{id}/report/download` |
| Registry | `/api/v1/registry/*` |

Swagger UI is available at:

```text
http://127.0.0.1:8000/docs
```

## Assessment Runtime

The runtime is registry-driven. Collector definitions are loaded from:

```text
app/config/assessment_registry/collectors.json
```

Lifecycle stages:

```text
QUEUED -> STARTING -> COLLECTING -> EVALUATING -> SCORING -> GENERATING_RECOMMENDATIONS -> COMPLETED
```

Runtime events are persisted and streamed over WebSockets. Key events include:

- `assessment.started`
- `collector.started`
- `collector.stdout`
- `collector.warning`
- `collector.completed`
- `collector.failed`
- `collector.timeout`
- `finding.generated`
- `scoring.completed`
- `recommendation.generated`
- `progress.update`
- `assessment.completed`

## PowerShell Collectors

Phase 7B replaces simulated collectors with real asynchronous PowerShell subprocess execution. Collectors must return structured JSON only:

```json
{
  "status": "success",
  "collector": "users_without_mfa",
  "tenant_id": "tenant-id",
  "timestamp": "2026-05-27T00:00:00Z",
  "findings": [],
  "metrics": {},
  "warnings": [],
  "errors": []
}
```

Implemented starter scripts live under:

```text
app/powershell/identity/
app/powershell/security/
app/powershell/compliance/
app/powershell/collaboration/
app/powershell/licensing/
```

The execution engine enforces subprocess isolation, timeout cleanup, retry handling, stdout/stderr capture, JSON result parsing, telemetry, and failure isolation.

## Reports

Phase 8A generates enterprise CRA reports from assessment findings, scoring, recommendations, and runtime evidence.

Generated artifacts:

```text
storage/reports/{assessment_id}/copilot-readiness-assessment.pdf
storage/reports/{assessment_id}/copilot-readiness-assessment.docx
```

The report engine includes:

- readiness score calculation
- severity, pillar, service, and pass/fail analytics
- dynamic executive summary
- dynamic observations and conclusion
- detailed service sections
- PDF rendering with ReportLab
- DOCX rendering with python-docx
- minimal fallback renderers for local environments without optional document libraries

Reports are tenant-scoped, assessment-scoped, authenticated, and downloadable only by authorized users.

## Validation

Run the backend test suite:

```bash
pytest -q
```

Run migrations:

```bash
alembic upgrade head
alembic check
```

Useful targeted checks:

```bash
pytest -q tests/test_phase7b_powershell_runtime.py
pytest -q tests/test_phase8_reports.py
```

## Notes

- `storage/reports/`, local SQLite databases, virtual environments, and `.env` files are ignored by git.
- The separate React/Vite frontend should live outside this backend repository, for example `/home/herb/cra-frontend`.
- Real Microsoft Graph collectors are reserved for a later phase; current PowerShell starter collectors use safe local/mock data while exercising real subprocess execution.
