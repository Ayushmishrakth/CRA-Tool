import { Link, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function MainLayout() {
  const { user, logout, loading } = useAuth();

  return (
    <div className="layout">
      <header className="header">
        <div className="brand">
          <Link to="/dashboard">CRA Platform</Link>
          <span className="badge">Copilot Readiness</span>
        </div>
        {user && (
          <div className="header-actions">
            <span className="user-email">{user.display_name || user.email}</span>
            <button type="button" onClick={logout} disabled={loading}>
              Logout
            </button>
          </div>
        )}
      </header>
      <main className="main">
        <Outlet />
      </main>
    </div>
  );
}
