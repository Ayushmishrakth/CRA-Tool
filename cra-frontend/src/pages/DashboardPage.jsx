import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import LoadingSpinner from "../components/LoadingSpinner";
import api from "../api/axiosClient";

export default function DashboardPage() {
  const { user, refreshUser } = useAuth();
  const [health, setHealth] = useState(null);
  const [apiError, setApiError] = useState(null);

  useEffect(() => {
    refreshUser();
    api
      .get("/health")
      .then((res) => setHealth(res.data))
      .catch((e) => setApiError(e.response?.data?.detail || e.message));
  }, [refreshUser]);

  if (!user) {
    return <LoadingSpinner label="Loading profile..." />;
  }

  return (
    <div className="dashboard">
      <h1>Dashboard</h1>
      <p className="welcome">
        Welcome, <strong>{user.display_name}</strong>
      </p>

      <section className="card">
        <h2>Your profile (GET /auth/me)</h2>
        <dl className="profile-grid">
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Role</dt>
          <dd>{user.role}</dd>
          <dt>Microsoft OID</dt>
          <dd className="mono">{user.microsoft_oid}</dd>
          <dt>Tenant ID</dt>
          <dd className="mono">{user.microsoft_tid}</dd>
          <dt>Connected tenants</dt>
          <dd>{user.connected_tenants?.join(", ") || "—"}</dd>
          <dt>Last login</dt>
          <dd>{user.last_login ? new Date(user.last_login).toLocaleString() : "—"}</dd>
        </dl>
      </section>

      <section className="card">
        <h2>Backend health (protected CRA session active)</h2>
        {health ? (
          <p className="success">API health: {health.status}</p>
        ) : apiError ? (
          <p className="error-text">{apiError}</p>
        ) : (
          <LoadingSpinner label="Checking API..." />
        )}
      </section>

      <section className="card muted">
        <h2>Token architecture</h2>
        <ul>
          <li>
            <strong>Microsoft ID token</strong> — used once at login, validated by FastAPI
          </li>
          <li>
            <strong>CRA JWT</strong> — stored in localStorage, sent on every API request
          </li>
        </ul>
      </section>
    </div>
  );
}
