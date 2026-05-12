import { useMemo, useState } from "react";
import { MessageSquareHeart } from "lucide-react";
import { submitFeedback } from "../api";

const TAGS = ["helpful", "confusing", "too_generic", "repetitive", "uncomfortable", "bug report"];

export default function FeedbackCard({ sessionId, reportId, onSubmitted }) {
  const [ratingUseful, setRatingUseful] = useState(null);
  const [ratingEngaging, setRatingEngaging] = useState(null);
  const [tags, setTags] = useState([]);
  const [comment, setComment] = useState("");
  const [consent, setConsent] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  const canSubmit = useMemo(
    () => Boolean(ratingUseful || ratingEngaging || tags.length || (consent && comment.trim())),
    [ratingUseful, ratingEngaging, tags, consent, comment]
  );

  function toggleTag(tag) {
    setTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError("");
    try {
      await submitFeedback({
        session_id: sessionId,
        report_id: reportId,
        feedback_type: "session",
        channel: "post_report",
        category: "story_report_experience",
        rating_useful: ratingUseful,
        rating_engaging: ratingEngaging,
        tags,
        comment: consent ? comment : "",
        consent_comment: consent,
      });
      setSuccess(true);
      onSubmitted?.();
    } catch (err) {
      setError(err.message || "Failed to submit feedback.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card feedback-card feedback-card-premium">
      <h3 className="feedback-card-title">
        <MessageSquareHeart size={22} aria-hidden />
        Help improve Psychometric Insights
      </h3>
      <p className="feedback-note">Optional. Your feedback helps improve the experience and will not affect your score.</p>
      {success ? (
        <p>Thanks — your feedback was recorded.</p>
      ) : (
        <form onSubmit={onSubmit}>
          <div className="rating-row">
            <span>How useful was this report?</span>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                type="button"
                key={`u-${n}`}
                className={`rating-button ${ratingUseful === n ? "selected" : ""}`}
                onClick={() => setRatingUseful(n)}
                aria-pressed={ratingUseful === n}
              >
                {n}
              </button>
            ))}
          </div>
          <div className="rating-row">
            <span>How engaging was the story?</span>
            {[1, 2, 3, 4, 5].map((n) => (
              <button
                type="button"
                key={`e-${n}`}
                className={`rating-button ${ratingEngaging === n ? "selected" : ""}`}
                onClick={() => setRatingEngaging(n)}
                aria-pressed={ratingEngaging === n}
              >
                {n}
              </button>
            ))}
          </div>
          <div className="feedback-actions">
            {TAGS.map((tag) => (
              <button
                type="button"
                key={tag}
                className={`tag-chip ${tags.includes(tag) ? "selected" : ""}`}
                onClick={() => toggleTag(tag)}
                aria-pressed={tags.includes(tag)}
              >
                {tag}
              </button>
            ))}
          </div>
          <label>
            Optional: what was confusing, uncomfortable, or especially helpful?
            <textarea maxLength={300} disabled={!consent} value={comment} onChange={(e) => setComment(e.target.value)} />
          </label>
          <label className="checkbox-field">
            <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>I agree to include this comment as product feedback.</span>
          </label>
          <button type="submit" disabled={!canSubmit || submitting}>
            {submitting ? "Submitting…" : "Submit feedback"}
          </button>
          {error && <p className="error">{error}</p>}
        </form>
      )}
    </div>
  );
}
