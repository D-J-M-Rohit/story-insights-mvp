import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { SessionContext } from "../App";
import { getNextScene } from "../api";
import SceneLoading from "./SceneLoading";
import SceneRenderer from "./SceneRenderer";
import TimerBar from "./TimerBar";

export default function AssessmentFlow() {
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
  const firstHoverRef = useRef(null);
  const hoverSwitchCountRef = useRef(0);

  const resetTelemetry = useCallback(() => {
    startRef.current = performance.now();
    hoverLogRef.current = [];
    firstHoverRef.current = null;
    hoverSwitchCountRef.current = 0;
    setSelected("");
  }, []);

  const loadFirst = useCallback(async () => {
    if (!session?.id) return;
    try {
      const first = await getNextScene({ session_id: session.id });
      setScene(first);
      resetTelemetry();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [session, resetTelemetry]);

  useEffect(() => {
    loadFirst();
  }, [loadFirst]);

  function onHover(optionId) {
    const t = Math.round(performance.now() - startRef.current);
    hoverLogRef.current.push({ option_id: optionId, t_ms: t });
    if (!firstHoverRef.current) {
      firstHoverRef.current = optionId;
      return;
    }
    const prev = hoverLogRef.current.length > 1 ? hoverLogRef.current[hoverLogRef.current.length - 2].option_id : optionId;
    if (prev !== optionId) hoverSwitchCountRef.current += 1;
  }

  async function submitCurrent(forceTimeout = false) {
    if (!scene || submitting) return;
    setSubmitting(true);
    setLoadingNext(true);
    setError("");
    const latency = Math.round(performance.now() - startRef.current);
    const telemetry = {
      latency_ms: latency,
      hover_log: hoverLogRef.current,
      hover_switch_count: hoverSwitchCountRef.current,
      changed_intent: Boolean(selected && firstHoverRef.current && selected !== firstHoverRef.current),
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
      } else {
        setError(e.message);
      }
    } finally {
      setSubmitting(false);
      setLoadingNext(false);
    }
  }

  if (loading) return <div className="page center">Loading scene...</div>;
  if (error && !scene) return <div className="page center error">{error}</div>;
  if (!scene) return <div className="page center">No scene.</div>;

  return (
    <div className="page">
      {loadingNext ? (
        <SceneLoading selectedChoiceText={lastChoiceText} />
      ) : (
        <>
          <TimerBar seconds={scene.time_limit_sec} sceneId={scene.id} onExpire={() => submitCurrent(true)} />
          <SceneRenderer
            scene={scene}
            selected={selected}
            onSelect={setSelected}
            onHover={onHover}
            onSubmit={() => submitCurrent(false)}
            submitting={submitting}
          />
        </>
      )}
      {error && <p className="error">{error}</p>}
      {error && lastPayload && (
        <button onClick={async () => {
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
        }}>
          Retry
        </button>
      )}
    </div>
  );
}
