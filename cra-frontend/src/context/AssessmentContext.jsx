import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useReducer,
  useRef,
} from "react";
import {
  getAssessment,
  getAssessmentEvents,
  getAssessmentFindings,
  getAssessmentJob,
  getAssessmentRecommendations,
  getAssessmentScore,
  getTenantAssessments,
  startAssessment as startAssessmentApi,
} from "../api/assessmentApi";
import { subscribeToAssessment } from "../services/websocketService";
import {
  makeTimelineEvent,
  normalizeAssessment,
  normalizeFinding,
  normalizeRecommendation,
  normalizeRuntimeEvent,
} from "../utils/assessmentFormatters";

const AssessmentContext = createContext(null);

const initialState = {
  assessments: [],
  activeAssessment: null,
  findings: [],
  recommendations: [],
  scores: null,
  runtimeJob: null,
  executionEvents: [],
  timelineEvents: [],
  websocketStatus: "disconnected",
  progress: 0,
  loading: false,
  error: null,
};

function reducer(state, action) {
  switch (action.type) {
    case "loading":
      return { ...state, loading: action.value, error: action.value ? null : state.error };
    case "error":
      return { ...state, loading: false, error: action.error };
    case "setAssessments":
      return { ...state, assessments: action.assessments, loading: false, error: null };
    case "setActive":
      return {
        ...state,
        activeAssessment: action.assessment,
        progress: action.assessment?.progress_pct ?? 0,
        loading: false,
        error: null,
      };
    case "setFindings":
      return { ...state, findings: action.findings };
    case "appendFinding":
      if (state.findings.some((finding) => finding.id === action.finding.id)) return state;
      return { ...state, findings: [action.finding, ...state.findings] };
    case "setRecommendations":
      return { ...state, recommendations: action.recommendations };
    case "setScores":
      return { ...state, scores: action.scores };
    case "setJob":
      return { ...state, runtimeJob: action.job };
    case "setEvents":
      return {
        ...state,
        executionEvents: action.events,
        timelineEvents: action.events.map(makeTimelineEvent).slice(0, 40),
      };
    case "appendEvent":
      if (state.executionEvents.some((event) => event.id === action.event.id)) return state;
      return { ...state, executionEvents: [action.event, ...state.executionEvents].slice(0, 120) };
    case "websocketStatus":
      return { ...state, websocketStatus: action.status };
    case "updateProgress":
      return {
        ...state,
        progress: action.progress,
        activeAssessment: state.activeAssessment
          ? { ...state.activeAssessment, progress_pct: action.progress }
          : state.activeAssessment,
      };
    case "appendTimeline":
      if (state.timelineEvents.some((event) => event.id === action.event.id)) return state;
      return {
        ...state,
        timelineEvents: [action.event, ...state.timelineEvents].slice(0, 40),
      };
    case "appendRecommendation":
      if (state.recommendations.some((item) => item.id === action.recommendation.id)) return state;
      return {
        ...state,
        recommendations: [action.recommendation, ...state.recommendations],
      };
    case "resetActive":
      return {
        ...state,
        activeAssessment: null,
        findings: [],
        recommendations: [],
        scores: null,
        runtimeJob: null,
        executionEvents: [],
        timelineEvents: [],
        progress: 0,
      };
    default:
      return state;
  }
}

export function AssessmentProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const unsubscribeRef = useRef(null);

  const fetchTenantAssessments = useCallback(async (tenantId, params = {}) => {
    dispatch({ type: "loading", value: true });
    try {
      const assessments = await getTenantAssessments(tenantId, params);
      dispatch({ type: "setAssessments", assessments });
      return assessments;
    } catch (err) {
      dispatch({ type: "error", error: err.response?.data?.detail || err.message });
      return [];
    }
  }, []);

  const fetchAssessment = useCallback(async (assessmentId) => {
    dispatch({ type: "loading", value: true });
    try {
      const [assessment, findings, recommendations, scores, events, job] = await Promise.all([
        getAssessment(assessmentId),
        getAssessmentFindings(assessmentId, { limit: 100 }),
        getAssessmentRecommendations(assessmentId),
        getAssessmentScore(assessmentId),
        getAssessmentEvents(assessmentId, { limit: 100 }).catch(() => []),
        getAssessmentJob(assessmentId).catch(() => null),
      ]);
      dispatch({ type: "setActive", assessment });
      dispatch({ type: "setFindings", findings });
      dispatch({ type: "setRecommendations", recommendations });
      dispatch({ type: "setScores", scores });
      dispatch({ type: "setEvents", events });
      dispatch({ type: "setJob", job });
      return assessment;
    } catch (err) {
      dispatch({ type: "error", error: err.response?.data?.detail || err.message });
      return null;
    }
  }, []);

  const startAssessment = useCallback(async (tenantId) => {
    dispatch({ type: "loading", value: true });
    try {
      const assessment = await startAssessmentApi(tenantId);
      dispatch({ type: "setActive", assessment });
      dispatch({ type: "setJob", job: assessment.job_id ? { id: assessment.job_id, status: "queued" } : null });
      dispatch({ type: "appendTimeline", event: makeTimelineEvent({ type: "assessment.started" }) });
      return assessment;
    } catch (err) {
      dispatch({ type: "error", error: err.response?.data?.detail || err.message });
      throw err;
    }
  }, []);

  const updateProgress = useCallback((progress) => {
    dispatch({ type: "updateProgress", progress });
  }, []);

  const appendFinding = useCallback((finding) => {
    dispatch({ type: "appendFinding", finding: normalizeFinding(finding) });
  }, []);

  const appendTimelineEvent = useCallback((event) => {
    const normalized = normalizeRuntimeEvent(event);
    dispatch({ type: "appendEvent", event: normalized });
    dispatch({ type: "appendTimeline", event: makeTimelineEvent(normalized) });
  }, []);

  const subscribeAssessment = useCallback((assessmentId) => {
    unsubscribeRef.current?.();
    dispatch({ type: "websocketStatus", status: "connecting" });
    unsubscribeRef.current = subscribeToAssessment(assessmentId, {
      onStatus: (status) => dispatch({ type: "websocketStatus", status }),
      onEvent: (event) => {
        const normalized = normalizeRuntimeEvent(event);
        const eventType = normalized.type ?? normalized.event;
        const payload = normalized.payload ?? {};
        appendTimelineEvent(normalized);
        if (eventType === "progress.update") {
          updateProgress(normalized.progress_pct ?? payload.progress_pct ?? 0);
        }
        if (eventType === "finding.generated" && normalized.finding) {
          appendFinding(normalized.finding);
        }
        if (eventType === "recommendation.generated" && normalized.recommendation) {
          dispatch({
            type: "appendRecommendation",
            recommendation: normalizeRecommendation(normalized.recommendation),
          });
        }
        if (eventType === "scoring.completed" && normalized.scores) {
          dispatch({ type: "setScores", scores: normalized.scores });
        }
        if (eventType === "assessment.completed" && normalized.assessment) {
          dispatch({ type: "setActive", assessment: normalizeAssessment(normalized.assessment) });
          updateProgress(100);
        }
        if (eventType === "assessment.failed") {
          dispatch({ type: "setJob", job: { id: payload.job_id, status: "failed", error_message: payload.error } });
        }
      },
    });
    return unsubscribeRef.current;
  }, [appendFinding, appendTimelineEvent, updateProgress]);

  const value = useMemo(
    () => ({
      ...state,
      fetchTenantAssessments,
      fetchAssessment,
      startAssessment,
      subscribeAssessment,
      updateProgress,
      appendFinding,
      appendTimelineEvent,
    }),
    [
      state,
      fetchTenantAssessments,
      fetchAssessment,
      startAssessment,
      subscribeAssessment,
      updateProgress,
      appendFinding,
      appendTimelineEvent,
    ]
  );

  return <AssessmentContext.Provider value={value}>{children}</AssessmentContext.Provider>;
}

export function useAssessments() {
  const context = useContext(AssessmentContext);
  if (!context) {
    throw new Error("useAssessments must be used within AssessmentProvider");
  }
  return context;
}
