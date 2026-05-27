import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, FileText, RotateCw } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useAssessments } from "../context/AssessmentContext";
import AssessmentProgress from "../components/assessment/AssessmentProgress";
import AssessmentStatusBadge from "../components/assessment/AssessmentStatusBadge";
import LoadingSpinner from "../components/LoadingSpinner";
import { formatDateTime, numberOrZero } from "../utils/assessmentFormatters";

const PAGE_SIZE = 8;

export default function AssessmentsPage() {
  const { user } = useAuth();
  const { assessments, loading, error, fetchTenantAssessments, startAssessment } = useAssessments();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const navigate = useNavigate();
  const tenantId = user?.microsoft_tid;

  useEffect(() => {
    if (tenantId) fetchTenantAssessments(tenantId, { limit: 100 });
  }, [tenantId, fetchTenantAssessments]);

  const filtered = useMemo(() => {
    return assessments.filter((assessment) => {
      const matchesStatus = status === "all" || assessment.status === status;
      const haystack = `${assessment.id} ${assessment.tenant_id} ${assessment.status}`.toLowerCase();
      return matchesStatus && haystack.includes(query.toLowerCase());
    });
  }, [assessments, query, status]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const rows = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const handleRestart = async (tenant) => {
    const assessment = await startAssessment(tenant);
    navigate(`/assessments/${assessment.id}`);
  };

  if (loading && assessments.length === 0) {
    return <LoadingSpinner label="Loading assessments..." />;
  }

  return (
    <div className="page-stack">
      <div className="page-header">
        <div>
          <h1>Assessments</h1>
          <p>Review Copilot readiness runs across your connected tenant.</p>
        </div>
        <button type="button" className="primary-action" onClick={() => handleRestart(tenantId)}>
          <RotateCw size={16} />
          Start Assessment
        </button>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <section className="panel">
        <div className="table-tools wide">
          <input
            value={query}
            onChange={(event) => {
              setPage(1);
              setQuery(event.target.value);
            }}
            placeholder="Search by tenant, status, or assessment ID"
          />
          <select
            value={status}
            onChange={(event) => {
              setPage(1);
              setStatus(event.target.value);
            }}
          >
            <option value="all">All statuses</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Assessment</th>
                <th>Status</th>
                <th>Score</th>
                <th>Tenant</th>
                <th>Findings</th>
                <th>Created</th>
                <th>Progress</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((assessment) => (
                <tr key={assessment.id}>
                  <td className="mono">{assessment.id.slice(0, 8)}</td>
                  <td><AssessmentStatusBadge status={assessment.status} /></td>
                  <td>{Math.round(numberOrZero(assessment.overall_score))}</td>
                  <td className="mono">{assessment.tenant_id}</td>
                  <td>
                    {assessment.total_findings ?? 0} total · {assessment.critical_findings ?? 0} critical
                  </td>
                  <td>{formatDateTime(assessment.created_at)}</td>
                  <td><AssessmentProgress value={assessment.progress_pct} compact /></td>
                  <td>
                    <div className="row-actions">
                      <Link className="icon-button" to={`/assessments/${assessment.id}`} aria-label="View assessment">
                        <Eye size={16} />
                      </Link>
                      <a
                        className={`icon-button ${assessment.report_path ? "" : "disabled"}`}
                        href={assessment.report_path || "#"}
                        aria-label="Open report"
                      >
                        <FileText size={16} />
                      </a>
                      <button type="button" className="icon-button" onClick={() => handleRestart(assessment.tenant_id)}>
                        <RotateCw size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="pagination">
          <button type="button" disabled={page === 1} onClick={() => setPage((v) => v - 1)}>
            Previous
          </button>
          <span>Page {page} of {totalPages}</span>
          <button type="button" disabled={page === totalPages} onClick={() => setPage((v) => v + 1)}>
            Next
          </button>
        </div>
      </section>
    </div>
  );
}
