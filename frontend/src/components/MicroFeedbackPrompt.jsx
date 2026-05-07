import { useEffect, useMemo, useState } from "react";
import { submitFeedback } from "../api";

export default function MicroFeedbackPrompt({ sessionId, sceneId, turn, onDismiss, onSubmitted }) {
  const enabled = String(import.meta.env.VITE_FEEDBACK_MICRO_PROMPT_ENABLED ?? "true").toLowerCase() !== "false";
  const [pace, setPace] = useState("");
  const [clarity, setClarity] = useState("");
  const [visible, setVisible] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const doneKey = useMemo(() => `story_insights_micro_feedback_done_${sessionId}`, [sessionId]);

  useEffect(() => {
    if (!sessionId || !enabled) return;
    const done = localStorage.getItem(doneKey) === "1";
    setVisible(!done && turn >= 2);
  }, [doneKey, sessionId, turn, enabled]);

  function close() {
    localStorage.setItem(doneKey, "1");
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
      localStorage.setItem(doneKey, "1");
      setVisible(false);
      onSubmitted?.();
    } catch (_) {
      // Do not break assessment flow on failure.
      localStorage.setItem(doneKey, "1");
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
