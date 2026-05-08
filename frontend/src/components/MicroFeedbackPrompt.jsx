import { useEffect, useMemo, useState } from "react";
import { submitFeedback } from "../api";

function buildMilestones(maxTurns) {
  const total = Number.isFinite(Number(maxTurns)) ? Math.max(0, Math.floor(Number(maxTurns))) : 0;
  const q1 = Math.floor(total * 0.25);
  const q3 = Math.floor(total * 0.75);
  const unique = [...new Set([q1, q3])].filter((v) => v > 0);
  return unique.sort((a, b) => a - b);
}

export default function MicroFeedbackPrompt({ sessionId, sceneId, turn, maxTurns, onDismiss, onSubmitted }) {
  const enabled = String(import.meta.env.VITE_FEEDBACK_MICRO_PROMPT_ENABLED ?? "true").toLowerCase() !== "false";
  const [pace, setPace] = useState("");
  const [clarity, setClarity] = useState("");
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [activeMilestone, setActiveMilestone] = useState(null);

  const milestones = useMemo(() => buildMilestones(maxTurns), [maxTurns]);
  const completedCount = Math.max(0, Number(turn || 0) - 1);

  const milestoneDoneKey = useMemo(
    () => (activeMilestone == null ? null : `story_insights_micro_feedback_done_${sessionId}_${activeMilestone}`),
    [activeMilestone, sessionId]
  );

  useEffect(() => {
    if (!sessionId || !enabled) return;
    const pendingMilestone = milestones.find((m) => {
      if (completedCount !== m) return false;
      const key = `story_insights_micro_feedback_done_${sessionId}_${m}`;
      return localStorage.getItem(key) !== "1";
    });
    setActiveMilestone(pendingMilestone ?? null);
    setVisible(Boolean(pendingMilestone));
  }, [sessionId, enabled, milestones, completedCount]);

  useEffect(() => {
    if (!visible) {
      setPace("");
      setClarity("");
    }
  }, [visible]);

  function close() {
    if (milestoneDoneKey) localStorage.setItem(milestoneDoneKey, "1");
    setVisible(false);
    onDismiss?.();
  }

  async function send() {
    if (!visible || submitting) return;
    setSubmitting(true);
    try {
      const tags = [pace, clarity].filter(Boolean);
      await submitFeedback({
        session_id: sessionId,
        scene_id: sceneId,
        turn,
        feedback_type: "micro",
        channel: "in_session",
        category: "pacing_clarity",
        tags,
      });
      if (milestoneDoneKey) localStorage.setItem(milestoneDoneKey, "1");
      setVisible(false);
      onSubmitted?.();
    } catch (_) {
      // Do not break assessment flow on failure.
      if (milestoneDoneKey) localStorage.setItem(milestoneDoneKey, "1");
      setVisible(false);
    } finally {
      setSubmitting(false);
    }
  }

  if (!enabled || !visible) return null;

  return (
    <div className="card micro-feedback">
      <p>How is the story pace so far?</p>
      <div className="feedback-actions">
        <button type="button" className={`tag-chip ${pace === "too_fast" ? "selected" : ""}`} onClick={() => setPace("too_fast")}>
          Too fast
        </button>
        <button type="button" className={`tag-chip ${pace === "about_right" ? "selected" : ""}`} onClick={() => setPace("about_right")}>
          About right
        </button>
        <button type="button" className={`tag-chip ${pace === "too_slow" ? "selected" : ""}`} onClick={() => setPace("too_slow")}>
          Too slow
        </button>
      </div>
      <p>Story clarity?</p>
      <div className="feedback-actions">
        <button type="button" className={`tag-chip ${clarity === "clear" ? "selected" : ""}`} onClick={() => setClarity("clear")}>
          Clear
        </button>
        <button type="button" className={`tag-chip ${clarity === "confusing" ? "selected" : ""}`} onClick={() => setClarity("confusing")}>
          Confusing
        </button>
      </div>
      <div className="feedback-actions">
        <button type="button" onClick={send} disabled={submitting}>
          {submitting ? "Sending..." : "Send"}
        </button>
        <button type="button" className="ghost-btn" onClick={close}>
          Skip
        </button>
      </div>
    </div>
  );
}
