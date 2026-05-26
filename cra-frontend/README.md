# CRA Frontend — Microsoft Auth Test App

React + MSAL React client for the CRA FastAPI backend.

## Why two tokens?

| Token | Who issues it | Used for |
|-------|---------------|----------|
| **Microsoft ID token** | Entra ID | Sent once to `POST /auth/login` |
| **CRA JWT** | CRA backend | Every API call (`Authorization: Bearer`) |

MSAL handles Microsoft login in the browser. The backend never sees Microsoft passwords.

## Install & run

```bash
cd cra-frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:3000

**Backend must be running:**

```bash
cd ..
source venv/bin/activate
uvicorn app.main:app --reload
```

## Azure App Registration

1. **SPA** platform redirect URI: `http://localhost:3000`
2. Enable **ID tokens** (implicit flow not required for popup; MSAL uses auth code + PKCE)
3. API permissions: `openid`, `profile`, `email`
4. Client ID must match `VITE_MSAL_CLIENT_ID` and backend `AZURE_CLIENT_ID`

## Test flow

1. Click **Login with Microsoft**
2. Complete Microsoft popup
3. Frontend sends `id_token` → backend returns CRA JWT
4. Dashboard loads profile from `GET /auth/me`
5. **Logout** clears CRA tokens and MSAL session

## Folder structure

```
src/
├── api/           # Axios client + auth API calls
├── auth/          # MSAL config & instance
├── components/    # ProtectedRoute, LoadingSpinner
├── context/       # AuthProvider (global auth state)
├── layouts/       # MainLayout with header
├── pages/         # Login, Dashboard
├── routes/        # React Router
├── services/      # Auth business helpers
└── utils/         # CRA token localStorage
```
