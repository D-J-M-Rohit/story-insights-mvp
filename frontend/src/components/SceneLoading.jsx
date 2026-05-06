import { useEffect, useState } from "react";

const messages = [
  "Adapting the story to your choice...",
  "Preparing the next decision point...",
  "Keeping the narrative consistent...",
];

export default function SceneLoading({ selectedChoiceText }) {
  const [index, setIndex] = useState(0);
  const [showSlowHint, setShowSlowHint] = useState(false);

  useEffect(() => {
    const rotate = setInterval(() => setIndex((i) => (i + 1) % messages.length), 1200);
    const slow = setTimeout(() => setShowSlowHint(true), 4000);
    return () => {
      clearInterval(rotate);
      clearTimeout(slow);
    };
  }, []);

  return (
    <div className="card pulse-card">
      <h3>{messages[index]}</h3>
      <div className="loading-dots" aria-hidden>
        <span />
        <span />
        <span />
      </div>
      {selectedChoiceText && <p className="muted">You chose: {selectedChoiceText}</p>}
      {showSlowHint && <p className="muted">This is taking a little longer because the AI is generating a fresh scenario.</p>}
    </div>
  );
}
