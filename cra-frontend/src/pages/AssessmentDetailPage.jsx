import { useEffect } from "react";
import { useParams } from "react-router-dom";
import AssessmentProgress from "../components/assessment/AssessmentProgress";
import AssessmentStatusBadge from "../components/assessment/AssessmentStatusBadge";
import AssessmentTimeline from "../components/assessment/AssessmentTimeline";
import AssessmentExecutionPanel from "../components/assessment/AssessmentExecutionPanel";
import CollectorStatusCard from "../components/assessment/CollectorStatusCard";
import DomainScoreGrid from "../components/assessment/DomainScoreGrid";
import FindingsTable from "../components/assessment/FindingsTable";
import RecommendationCard from "../components/assessment/RecommendationCard";
import DomainRadarChart from "../components/charts/DomainRadarChart";
import ReadinessRadialChart from "../components/charts/ReadinessRadialChart";
import LoadingSpinner from "../components/LoadingSpinner";
import { useAssessments } from "../context/AssessmentContext";
import {
  formatDateTime,
  formatDuration,
  numberOrZero,
} from "../utils/assessmentFormatters";

export default function AssessmentDetailPage() {
  const { assessmentId } = useParams();
  const {
    activeAssessment,
    findings,
    recommendations,
    scores,
    runtimeJob,
    executionEvents,
    timelineEvents,
    websocketStatus,
    progress,
    loading,
    error,
    fetchAssessment,
    subscribeAssessment,
  } = useAssessments();

  useEffect(() => {
    if (!assessmentId) return undefined;
    fetchAssessment(assessmentId);
    return subscribeAssessment(assessmentId);
  }, [assessmentId, fetchAssessment, subscribeAssessment]);

  if (loading && !activeAssessment) {
    return <LoadingSpinner label="Loading assessment..." />;
  }

  if (error && !activeAssessment) {
    return <div className="error-banner">{error}</div>;
  }

  const assessment = activeAssessment;
  if (!assessment) return null;
  const completedAt = assessment.status === "completed" ? assessment.updated_at : null;
  const overall = assessment.overall_score ?? scores?.overall_score ?? 0;

  return (
    <div className="page-stack assessment-detail">
      <div className="assessment-hero">
        <div>
          <span className="eyebrow">Tenant</span>
          <h1>{assessment.tenant_id}</h1>
          <div className="hero-meta">
            <AssessmentStatusBadge status={assessment.status} />
            <span>Started {formatDateTime(assessment.created_at)}</span>
            <span>Completed {formatDateTime(completedAt)}</span>
            <span>Duration {formatDuration(assessment.created_at, completedAt)}</span>
          </div>
        </div>
        <AssessmentProgress value={progress} />
      </div>

      {error && <div className="error-banner">{error}</div>}

      <section className="detail-grid">
        <ReadinessRadialChart score={overall} />
        <div className="metric-grid">
          <article className="metric-card">
            <span>Total findings</span>
            <strong>{assessment.total_findings ?? findings.length}</strong>
          </article>
          <article className="metric-card">
            <span>Critical findings</span>
            <strong>{assessment.critical_findings ?? 0}</strong>
          </article>
          <article className="metric-card">
            <span>High findings</span>
            <strong>{assessment.high_findings ?? 0}</strong>
          </article>
          <article className="metric-card">
            <span>Score status</span>
            <strong>{numberOrZero(overall) >= 75 ? "Ready" : "Needs work"}</strong>
          </article>
        </div>
      </section>

      <DomainScoreGrid assessment={assessment} scores={scores} />

      <section className="two-column">
        <DomainRadarChart assessment={assessment} scores={scores} />
        <CollectorStatusCard progress={progress} />
      </section>

      <AssessmentTimeline events={timelineEvents} connectionStatus={websocketStatus} />

      <AssessmentExecutionPanel
        job={runtimeJob}
        events={executionEvents}
        connectionStatus={websocketStatus}
      />

      <FindingsTable findings={findings} />

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Recommendations</h2>
            <p>Prioritized remediation actions for improving Copilot readiness.</p>
          </div>
        </div>
        <div className="recommendations-grid">
          {(recommendations.length
            ? recommendations
            : [
                {
                  id: "empty-recommendation",
                  title: "No generated recommendations yet",
                  severity: "info",
                  impact: "Recommendations will appear when backend scoring produces remediation guidance.",
                  priority_score: 0,
                  remediation_steps: ["Keep the assessment running until findings and scoring complete."],
                },
              ]
          ).map((recommendation) => (
            <RecommendationCard key={recommendation.id} recommendation={recommendation} />
          ))}
        </div>
      </section>
    </div>
  );
}
