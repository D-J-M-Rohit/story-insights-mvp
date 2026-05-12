import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SessionContext } from "../App";
import { getNextScene } from "../api";
import AppHeader from "./AppHeader";
import SceneLoading from "./SceneLoading";
import MicroFeedbackPrompt from "./MicroFeedbackPrompt";
import SceneRenderer from "./SceneRenderer";
import TimerBar from "./TimerBar";

export default function AssessmentFlow({ initialScene = null }) {
  const { session } = useContext(SessionContext);
  const [scene, setScene] = useState(null);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingNext, setLoadingNext] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [lastPayload, setLastPayload] = useState(null);
  const [lastChoiceText, setLastChoiceText] = useState("");
  const navigate = useNavigate();

  const startRef = useRef(performance.now());
  const hoverLogRef = useRef([]);
  const hoverDwellRef = useRef({ A: 0, B: 0, C: 0 });
  const hoverStartRef = useRef({});
  const currentHoverRef = useRef(null);
  const firstHoverRef = useRef(null);
  const lastHoverRef = useRef(null);
  const optionViewOrderRef = useRef([]);
  const focusLostCountRef = useRef(0);
  const hoverSwitchCountRef = useRef(0);

  const resetTelemetry = useCallback(() => {
    startRef.current = performance.now();
    hoverLogRef.current = [];
    hoverDwellRef.current = { A: 0, B: 0, C: 0 };
    hoverStartRef.current = {};
    currentHoverRef.current = null;
    firstHoverRef.current = null;
    lastHoverRef.current = null;
    optionViewOrderRef.current = [];
    focusLostCountRef.current = 0;
    hoverSwitchCountRef.current = 0;
    setSelected("");
  }, []);

  useEffect(() => {
    function onVisibility() {
      if (document.visibilityState === "hidden") focusLostCountRef.current += 1;
    }
    function onBlur() {
      focusLostCountRef.current += 1;
    }
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    return () => {
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("blur", onBlur);
    };
  }, []);

  const sessionId = session?.id;

  const loadFirst = useCallback(async () => {
    if (!sessionId) return;
    try {
      const first = await getNextScene({ session_id: sessionId });
      setScene(first);
      resetTelemetry();
    } catch (e) {
      if (e.status === 410 || String(e.message || "").includes("assessment_complete")) {
        navigate(`/report/${sessionId}`);
        return;
      }
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [sessionId, resetTelemetry, navigate]);

  useEffect(() => {
    if (!sessionId) return;
    if (initialScene && initialScene.id) {
      setScene(initialScene);
      setLoading(false);
      setError("");
      resetTelemetry();
      return;
    }
    setLoading(true);
    loadFirst();
    // Depend on ids only — full object identities can churn and refetch in a tight loop.
  }, [sessionId, initialScene?.id, loadFirst, resetTelemetry]);

  function onHover(optionId) {
    const t = Math.round(performance.now() - startRef.current);
    if (hoverLogRef.current.length < 80) hoverLogRef.current.push({ event: "enter", option_id: optionId, t_ms: t });
    hoverStartRef.current[optionId] = t;
    currentHoverRef.current = optionId;
    lastHoverRef.current = optionId;
    if (!firstHoverRef.current) {
      firstHoverRef.current = optionId;
    }
    if (!optionViewOrderRef.current.includes(optionId)) optionViewOrderRef.current.push(optionId);
    const prev = hoverLogRef.current.length > 1 ? hoverLogRef.current[hoverLogRef.current.length - 2].option_id : optionId;
    if (prev && prev !== optionId) hoverSwitchCountRef.current += 1;
  }

  function onLeave(optionId) {
    const t = Math.round(performance.now() - startRef.current);
    if (hoverLogRef.current.length < 80) hoverLogRef.current.push({ event: "leave", option_id: optionId, t_ms: t });
    const start = hoverStartRef.current[optionId];
    if (start != null) {
      hoverDwellRef.current[optionId] = (hoverDwellRef.current[optionId] || 0) + Math.max(0, t - start);
      delete hoverStartRef.current[optionId];
    }
    if (currentHoverRef.current === optionId) currentHoverRef.current = null;
  }

  async function submitCurrent(forceTimeout = false) {
    if (!scene || submitting) return;
    setSubmitting(true);
    setLoadingNext(true);
    setError("");
    const latency = Math.round(performance.now() - startRef.current);
    if (currentHoverRef.current) onLeave(currentHoverRef.current);
    const dwell = hoverDwellRef.current;
    const dominant = Object.entries(dwell).sort((a, b) => b[1] - a[1])[0]?.[0] || null;
    const telemetry = {
      latency_ms: latency,
      latency_ratio: scene.time_limit_sec ? latency / (scene.time_limit_sec * 1000) : 0,
      hover_log: hoverLogRef.current,
      hover_dwell_ms_by_option: dwell,
      hover_switch_count: hoverSwitchCountRef.current,
      first_hovered_option_id: firstHoverRef.current,
      last_hovered_option_id: lastHoverRef.current,
      option_view_order: optionViewOrderRef.current,
      focus_lost_count: focusLostCountRef.current,
      browser_focus_lost: focusLostCountRef.current > 0,
      changed_intent: Boolean(
        selected &&
          ((firstHoverRef.current && selected !== firstHoverRef.current) ||
            (dominant && selected !== dominant))
      ),
      timed_out: forceTimeout,
    };
    const chosen = scene.options.find((o) => o.id === selected);
    setLastChoiceText(forceTimeout ? "No selection (timed out)" : chosen?.text || "No selection");
    const payload = {
      session_id: session.id,
      scene_id: scene.id,
      choice_id: forceTimeout ? null : selected || null,
      telemetry,
    };
    setLastPayload(payload);
    try {
      const next = await getNextScene(payload);
      setScene(next);
      resetTelemetry();
      setLastPayload(null);
    } catch (e) {
      if (e.status === 410 || e.message === "assessment_complete") {
        navigate(`/report/${session.id}`);
      } else if (e.status === 429 || e.message === "rate_limit_exceeded") {
        setError("Too many requests. Please try again in a moment.");
      } else {
        setError(e.message);
      }
    } finally {
      setSubmitting(false);
      setLoadingNext(false);
    }
  }

  if (loading) {
    return (
      <>
        <AppHeader title="Assessment" />
        <div className="page center app-loading" role="status">
          Loading scene…
        </div>
      </>
    );
  }
  if (error && !scene) {
    return (
      <>
        <AppHeader title="Assessment" />
        <div className="page center error">{error}</div>
      </>
    );
  }
  if (!scene) {
    return (
      <>
        <AppHeader title="Assessment" />
        <div className="page center">No scene.</div>
      </>
    );
  }

  const maxTurns = session?.max_turns ?? "?";
  const scenarioLabel = session?.scenario ?? "—";

  return (
    <>
      <AppHeader title="Assessment" />
      <div className="page">
        {loadingNext ? (
          <SceneLoading selectedChoiceText={lastChoiceText} />
        ) : (
          <>
            <div className="assessment-progress no-print">
              <span className="scenario-pill" title="Scenario">
                Scenario: <strong>{scenarioLabel}</strong>
              </span>
              <span className="meta-pill" aria-label={`Turn ${scene.turn} of ${maxTurns}`}>
                Turn {scene.turn} of {maxTurns}
              </span>
            </div>
            {import.meta.env.DEV && scene?.scene_metadata?.target_construct && (
              <p className="muted small">
                Target: {scene.scene_metadata.target_construct} · Difficulty: {scene.scene_metadata.difficulty}
              </p>
            )}
            {import.meta.env.DEV && <p className="muted small">Telemetry active</p>}
            {import.meta.env.DEV && Array.isArray(scene?.scene_metadata?.context_fragment_ids) && (
              <p className="muted small">Context: {scene.scene_metadata.context_fragment_ids.length} anchors</p>
            )}
            <MicroFeedbackPrompt
              sessionId={session.id}
              sceneId={scene.id}
              turn={scene.turn}
              maxTurns={session.max_turns}
            />
            <TimerBar seconds={scene.time_limit_sec} sceneId={scene.id} onExpire={() => submitCurrent(true)} />
            <SceneRenderer
              scene={scene}
              selected={selected}
              onSelect={setSelected}
              onHover={onHover}
              onLeave={onLeave}
              onSubmit={() => submitCurrent(false)}
              submitting={submitting}
            />
          </>
        )}
        {error && <p className="error">{error}</p>}
        {error && lastPayload && (
          <button type="button" onClick={async () => {
            setError("");
            setLoadingNext(true);
            try {
              const next = await getNextScene(lastPayload);
              setScene(next);
              resetTelemetry();
              setLastPayload(null);
            } catch (e) {
              setError(e.message);
            } finally {
              setLoadingNext(false);
            }
          }}
          >
            Retry
          </button>
        )}
      </div>
    </>
  );
}
