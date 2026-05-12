import { useEffect, useState } from "react";

const messages = [
  "Adapting the next decision point…",
  "Preparing the next scene…",
  "Keeping the narrative consistent…",
];

export default function SceneLoading({ selectedChoiceText }) {
  const [index, setIndex] = useState(0);
  const [showSlowHint, setShowSlowHint] = useState(false);

  useEffect(() => {
    const rotate = setInterval(() => setIndex((i) => (i + 1) % messages.length), 1400);
    const slow = setTimeout(() => setShowSlowHint(true), 4000);
    return () => {
      clearInterval(rotate);
      clearTimeout(slow);
    };
  }, []);

  return (
    <div className="card pulse-card" role="status" aria-live="polite">
      <h3 style={{ marginTop: 0 }}>{messages[index]}</h3>
      <div className="shimmer-bar" aria-hidden />
      <div className="loading-dots" aria-hidden>
        <span />
        <span />
        <span />
      </div>
      {selectedChoiceText && (
        <p className="muted">
          <strong>Previous choice:</strong> {selectedChoiceText}
        </p>
      )}
      {showSlowHint && (
        <p className="muted small">This is taking a little longer while the next scene is generated.</p>
      )}
    </div>
  );
}
