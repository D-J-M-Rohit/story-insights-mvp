import { GitBranch } from "lucide-react";

export default function SceneRenderer({ scene, selected, onSelect, onHover, onLeave, onSubmit, submitting }) {
  return (
    <div className="card story-scene-card">
      <div className="story-card-title-row">
        <GitBranch className="story-branch-icon" size={26} strokeWidth={2} aria-hidden />
        <div>
          <h2 style={{ margin: 0 }}>
            Turn {scene.turn}: {scene.title}
          </h2>
        </div>
      </div>
      <p className="story-narrative">{scene.scene}</p>
      <div className="options" role="group" aria-label="Choose an option">
        {scene.options.map((opt) => (
          <button
            key={opt.id}
            type="button"
            className={`option ${selected === opt.id ? "selected" : ""}`}
            onMouseEnter={() => onHover(opt.id)}
            onMouseLeave={() => onLeave?.(opt.id)}
            onClick={() => onSelect(opt.id)}
            aria-pressed={selected === opt.id}
          >
            <span className="badge">{opt.id}</span>
            {opt.text}
          </button>
        ))}
      </div>
      <div className="submit-row">
        <button type="button" onClick={onSubmit} disabled={submitting || !selected}>
          {submitting ? "Submitting…" : "Submit choice"}
        </button>
      </div>
    </div>
  );
}
