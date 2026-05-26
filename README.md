# CRA Backend

**Copilot Readiness Assessment (CRA)** — enterprise FastAPI backend for Microsoft 365.

## Authentication model

This platform does **not** use email/password registration.

| Layer | Technology |
|-------|------------|
| Frontend login | MSAL React (frontend team) |
| Identity provider | Microsoft Entra ID |
| Backend login input | Microsoft **ID token** |
| Backend API security | **CRA internal JWT** (Bearer) |

### Flow

```text
MSAL React → Microsoft Login → Microsoft ID Token
    → POST /api/v1/auth/login { "id_token": "..." }
    → Backend validates token (Entra JWKS)
    → Create/update user in database
    → Return CRA access_token + refresh_token
    → Frontend uses CRA JWT for all API calls
```

## Project structure

```
app/
├── core/
│   ├── config.py       # Settings (.env)
│   ├── security.py     # CRA JWT create/verify
│   ├── microsoft.py    # Microsoft ID token validation (PyJWT)
│   ├── msal_client.py  # MSAL factory (Graph / Phase 4)
│   └── auth.py         # FastAPI dependencies (Bearer, RBAC)
├── routes/auth.py      # login, refresh, logout, me
├── services/auth_service.py
├── schemas/auth_schema.py
├── models/user_model.py
└── db/database.py
```

## Installation

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set AZURE_CLIENT_ID, SECRET_KEY in .env
uvicorn app.main:app --reload
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | CRA JWT signing key |
| `ALGORITHM` | Yes | Default `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Access token TTL |
| `AZURE_CLIENT_ID` | Yes | Entra app registration client ID |
| `AZURE_TENANT_ID` | Yes | Tenant ID or `common` (multi-tenant) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | Default 7 |

## API endpoints (Phase 3)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/v1/auth/login` | No | Microsoft ID token → CRA JWT |
| POST | `/api/v1/auth/refresh` | No | New CRA token pair |
| POST | `/api/v1/auth/logout` | Optional Bearer | Revoke tokens |
| GET | `/api/v1/auth/me` | CRA Bearer | User profile |

**Not implemented (by design):** register, password login.

## Example: login

Request (from MSAL React after `loginPopup` / `acquireTokenSilent`):

```json
POST /api/v1/auth/login
{
  "id_token": "<microsoft-id-token>"
}
```

Response:

```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## Example: protected call

```bash
curl http://127.0.0.1:8000/api/v1/auth/me \
  -H "Authorization: Bearer <CRA_ACCESS_TOKEN>"
```

## Swagger

1. Call `POST /auth/login` with a real Microsoft `id_token`
2. Copy `access_token`
3. Click **Authorize** → paste token
4. Call `GET /auth/me`

## CRA JWT claims

| Claim | Description |
|-------|-------------|
| `sub` | CRA user ID |
| `tid` | Primary Microsoft tenant ID |
| `email` | User email |
| `role` | RBAC role |
| `connected_tenants` | Tenant IDs user may access |
| `jti` | Token ID (revocation on logout) |

## Multi-tenant

- `User.microsoft_tid` — home tenant
- `UserTenantConnection` — linked tenants
- `connected_tenants` in JWT for tenant-scoped APIs
- `AZURE_TENANT_ID=common` for multi-tenant app registration

## Protecting routes

```python
from app.core.auth import get_current_active_user, require_roles
from app.models.user_model import User, UserRole

@router.get("/admin")
def admin_only(user: User = Depends(require_roles(UserRole.ADMIN))):
    ...
```

## Phase 4+ (prepared)

- Microsoft Graph API (`msal_client.py`)
- Admin consent / app registration
- WebSocket auth (same CRA JWT validation)
- OAuth token exchange (OBO)
