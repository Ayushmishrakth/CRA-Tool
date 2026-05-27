import {
  Activity,
  CheckCircle2,
  Clock3,
  DatabaseZap,
  RotateCw,
  ServerCog,
  TerminalSquare,
  XCircle,
} from "lucide-react";
import { formatDateTime } from "../../utils/assessmentFormatters";

const EVENT_ICON = {
  "assessment.started": ServerCog,
  "collector.started": DatabaseZap,
  "collector.completed": CheckCircle2,
  "collector.failed": XCircle,
  "finding.generated": Activity,
  "scoring.completed": CheckCircle2,
  "recommendation.generated": TerminalSquare,
  "assessment.completed": CheckCircle2,
  "assessment.failed": XCircle,
};

function eventLabel(type) {
  return String(type || "runtime.event").replaceAll(".", " ");
}

export default function AssessmentExecutionPanel({
  job,
  events = [],
  connectionStatus = "disconnected",
}) {
  const collectorEvents = events.filter((event) => event.type?.startsWith("collector."));
  const liveEvents = events.slice(0, 14);
  const retryEvents = events.filter((event) => event.payload?.retry || event.payload?.throttled);

  return (
    <section className="panel execution-panel">
      <div className="panel-header">
        <div>
          <h2>Runtime Execution</h2>
          <p>Worker orchestration, collector activity, and persisted runtime events.</p>
        </div>
        <span className={`connection-pill ${connectionStatus}`}>{connectionStatus}</span>
      </div>

      <div className="execution-summary">
        <article>
          <span>Job status</span>
          <strong>{job?.status ?? "queued"}</strong>
        </article>
        <article>
          <span>Stage</span>
          <strong>{job?.current_stage ?? "queued"}</strong>
        </article>
        <article>
          <span>Worker</span>
          <strong className="mono">{job?.worker_id ?? "-"}</strong>
        </article>
        <article>
          <span>Runtime</span>
          <strong>{job?.metadata?.runtime ?? "phase7a"}</strong>
        </article>
      </div>

      {job?.error_message && <div className="error-banner">{job.error_message}</div>}

      <div className="runtime-grid">
        <div className="runtime-column">
          <div className="runtime-column-title">
            <DatabaseZap size={16} />
            <span>Collectors</span>
          </div>
          {collectorEvents.length === 0 && (
            <p className="muted-text">Collector events will appear when the worker starts.</p>
          )}
          {collectorEvents.slice(0, 8).map((event) => {
            const Icon = EVENT_ICON[event.type] || Clock3;
            return (
              <article className="runtime-event" key={event.id}>
                <Icon size={16} />
                <div>
                  <strong>{event.payload?.collector ?? event.payload?.parameter_key ?? eventLabel(event.type)}</strong>
                  <span>{eventLabel(event.type)}</span>
                </div>
                <time>{formatDateTime(event.timestamp)}</time>
              </article>
            );
          })}
        </div>

        <div className="runtime-column">
          <div className="runtime-column-title">
            <RotateCw size={16} />
            <span>Retries & throttling</span>
          </div>
          {retryEvents.length === 0 && <p className="muted-text">No retry or throttling events recorded.</p>}
          {retryEvents.slice(0, 6).map((event) => (
            <article className="runtime-event" key={event.id}>
              <RotateCw size={16} />
              <div>
                <strong>{event.payload?.parameter_key ?? eventLabel(event.type)}</strong>
                <span>{event.payload?.retry ? "Retry scheduled" : "Throttle handled"}</span>
              </div>
              <time>{formatDateTime(event.timestamp)}</time>
            </article>
          ))}
        </div>
      </div>

      <div className="runtime-column runtime-log">
        <div className="runtime-column-title">
          <ServerCog size={16} />
          <span>Execution log</span>
        </div>
        {liveEvents.length === 0 && <p className="muted-text">Waiting for runtime events.</p>}
        {liveEvents.map((event) => {
          const Icon = EVENT_ICON[event.type] || Activity;
          return (
            <article className="runtime-event" key={event.id}>
              <Icon size={16} />
              <div>
                <strong>{eventLabel(event.type)}</strong>
                <span>
                  {event.payload?.stage ??
                    event.payload?.parameter_key ??
                    event.payload?.finding?.parameter_name ??
                    event.payload?.recommendation?.title ??
                    event.severity}
                </span>
              </div>
              <time>{formatDateTime(event.timestamp)}</time>
            </article>
          );
        })}
      </div>
    </section>
  );
}
