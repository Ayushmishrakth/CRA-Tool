import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { PlayCircle } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useAssessments } from "../context/AssessmentContext";
import AssessmentStatusBadge from "../components/assessment/AssessmentStatusBadge";
import FindingsSeverityChart from "../components/charts/FindingsSeverityChart";
import ScoreTrendChart from "../components/charts/ScoreTrendChart";
import LoadingSpinner from "../components/LoadingSpinner";
import api from "../api/axiosClient";
import {
  buildScoreTrend,
  formatDateTime,
  numberOrZero,
} from "../utils/assessmentFormatters";

export default function DashboardPage() {
  const { user, refreshUser } = useAuth();
  const {
    assessments,
    loading: assessmentLoading,
    error: assessmentError,
    fetchTenantAssessments,
    startAssessment,
  } = useAssessments();
  const [health, setHealth] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    refreshUser();
    api
      .get("/health")
      .then((res) => setHealth(res.data))
      .catch((e) => setApiError(e.response?.data?.detail || e.message));
  }, [refreshUser]);

  useEffect(() => {
    if (user?.microsoft_tid) {
      fetchTenantAssessments(user.microsoft_tid, { limit: 100 });
    }
  }, [user?.microsoft_tid, fetchTenantAssessments]);

  const summary = useMemo(() => {
    const scored = assessments.filter((assessment) => assessment.overall_score != null);
    const avg =
      scored.length === 0
        ? 0
        : scored.reduce((sum, item) => sum + numberOrZero(item.overall_score), 0) / scored.length;
    return {
      total: assessments.length,
      average: Math.round(avg),
      critical: assessments.reduce((sum, item) => sum + numberOrZero(item.critical_findings), 0),
      recent: [...assessments]
        .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
        .slice(0, 5),
      severityData: [
        {
          name: "critical",
          value: assessments.reduce((sum, item) => sum + numberOrZero(item.critical_findings), 0),
        },
        {
          name: "high",
          value: assessments.reduce((sum, item) => sum + numberOrZero(item.high_findings), 0),
        },
        {
          name: "medium",
          value: Math.max(
            0,
            assessments.reduce((sum, item) => sum + numberOrZero(item.total_findings), 0) -
              assessments.reduce((sum, item) => sum + numberOrZero(item.critical_findings), 0) -
              assessments.reduce((sum, item) => sum + numberOrZero(item.high_findings), 0)
          ),
        },
      ],
    };
  }, [assessments]);

  const handleStartAssessment = async () => {
    const assessment = await startAssessment(user.microsoft_tid);
    setShowConfirm(false);
    navigate(`/assessments/${assessment.id}`);
  };

  if (!user) {
    return <LoadingSpinner label="Loading profile..." />;
  }

  return (
    <div className="dashboard page-stack">
      <div className="page-header">
        <div>
          <h1>Dashboard</h1>
          <p className="welcome">
            Welcome, <strong>{user.display_name}</strong>
          </p>
        </div>
        <button type="button" className="primary-action" onClick={() => setShowConfirm(true)}>
          <PlayCircle size={16} />
          Start Assessment
        </button>
      </div>

      {assessmentError && <div className="error-banner">{assessmentError}</div>}

      <section className="metric-grid dashboard-metrics">
        <article className="metric-card">
          <span>Total assessments</span>
          <strong>{summary.total}</strong>
        </article>
        <article className="metric-card">
          <span>Average readiness</span>
          <strong>{summary.average}</strong>
        </article>
        <article className="metric-card">
          <span>Critical findings</span>
          <strong>{summary.critical}</strong>
        </article>
        <article className="metric-card">
          <span>Current tenant</span>
          <strong className="small-metric">{user.microsoft_tid}</strong>
        </article>
      </section>

      <section className="two-column">
        <ScoreTrendChart data={buildScoreTrend(assessments)} />
        <FindingsSeverityChart data={summary.severityData} />
      </section>

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Recent assessments</h2>
            <p>Latest readiness workflow runs for this tenant.</p>
          </div>
        </div>
        {assessmentLoading && assessments.length === 0 ? (
          <LoadingSpinner label="Loading assessment history..." />
        ) : (
          <div className="recent-list">
            {summary.recent.map((assessment) => (
              <button
                type="button"
                className="recent-row"
                key={assessment.id}
                onClick={() => navigate(`/assessments/${assessment.id}`)}
              >
                <span className="mono">{assessment.id.slice(0, 8)}</span>
                <AssessmentStatusBadge status={assessment.status} />
                <strong>{Math.round(numberOrZero(assessment.overall_score))}</strong>
                <span>{formatDateTime(assessment.created_at)}</span>
              </button>
            ))}
            {summary.recent.length === 0 && <p className="muted-text">No assessments yet.</p>}
          </div>
        )}
      </section>

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

      {showConfirm && (
        <div className="modal-backdrop" role="presentation">
          <div className="modal" role="dialog" aria-modal="true" aria-labelledby="start-title">
            <h2 id="start-title">Start tenant assessment?</h2>
            <p>
              CRA will queue a new workflow for tenant <span className="mono">{user.microsoft_tid}</span>.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn-secondary inline" onClick={() => setShowConfirm(false)}>
                Cancel
              </button>
              <button type="button" className="primary-action" onClick={handleStartAssessment}>
                Start Assessment
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
