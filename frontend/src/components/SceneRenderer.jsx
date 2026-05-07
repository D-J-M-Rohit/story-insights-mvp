export default function SceneRenderer({ scene, selected, onSelect, onHover, onLeave, onSubmit, submitting }) {
  return (
    <div className="card">
      <h2>
        Turn {scene.turn}: {scene.title}
      </h2>
      <p>{scene.scene}</p>
      <div className="options">
        {scene.options.map((opt) => (
          <button
            key={opt.id}
            className={`option ${selected === opt.id ? "selected" : ""}`}
            onMouseEnter={() => onHover(opt.id)}
            onMouseLeave={() => onLeave?.(opt.id)}
            onClick={() => onSelect(opt.id)}
          >
            <span className="badge">{opt.id}</span>
            {opt.text}
          </button>
        ))}
      </div>
      <button onClick={onSubmit} disabled={submitting || !selected}>
        {submitting ? "Submitting..." : "Submit"}
      </button>
    </div>
  );
}
