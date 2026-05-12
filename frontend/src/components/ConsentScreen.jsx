import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase, GraduationCap, Siren } from "lucide-react";
import { createSession } from "../api";
import { SessionContext } from "../App";
import AppHeader from "./AppHeader";
import BrandLogo from "./BrandLogo";

const SCENARIOS = [
  {
    id: "workplace",
    title: "Workplace",
    description: "Collaboration, deadlines, and professional tradeoffs.",
    Icon: Briefcase,
  },
  {
    id: "school",
    title: "School",
    description: "Study habits, peers, and academic pressure.",
    Icon: GraduationCap,
  },
  {
    id: "emergency",
    title: "Emergency",
    description: "Time-critical choices under stress.",
    Icon: Siren,
  },
];

export default function ConsentScreen() {
  const [scenario, setScenario] = useState("workplace");
  const [maxTurns, setMaxTurns] = useState(20);
  const [consented, setConsented] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { setSession } = useContext(SessionContext);

  async function start() {
    if (!consented) return;
    setLoading(true);
    setError("");
    try {
      const session = await createSession({ scenario, max_turns: Number(maxTurns) });
      setSession(session);
      navigate(`/assessment/${session.id}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <AppHeader title="Start session" />
      <div className="page consent-page">
        <div className="card">
          <BrandLogo size="md" showText />
          <h2 style={{ marginTop: "16px" }}>Start a Decision Journey</h2>
          <p className="muted">Choose a scenario and how many turns you want. You can stop early by completing choices.</p>

          <h3 className="small" style={{ marginTop: "20px", fontWeight: 700, color: "var(--text)" }}>
            Scenario
          </h3>
          <div className="consent-scenarios">
            {SCENARIOS.map(({ id, title, description, Icon }) => (
              <button
                key={id}
                type="button"
                className={`scenario-card ${scenario === id ? "selected" : ""}`}
                onClick={() => setScenario(id)}
                aria-pressed={scenario === id}
              >
                <Icon size={22} aria-hidden />
                <h4>{title}</h4>
                <p>{description}</p>
              </button>
            ))}
          </div>

          <label>
            Max turns
            <select value={maxTurns} onChange={(e) => setMaxTurns(e.target.value)}>
              <option value="10">10</option>
              <option value="15">15</option>
              <option value="20">20</option>
              <option value="25">25</option>
              <option value="30">30</option>
            </select>
          </label>

          <div className="card" style={{ marginTop: "18px", background: "var(--surface-strong)" }}>
            <h3 style={{ marginTop: 0 }}>Before you begin</h3>
            <ul className="consent-list">
              <li>This experience is <strong>experimental reflection</strong>, not therapy or coaching.</li>
              <li>It is <strong>not</strong> a clinical, diagnostic, or hiring assessment.</li>
              <li>Your choices generate a <strong>deterministic report</strong> from the backend.</li>
              <li>AI writes scenes; <strong>scores are computed separately</strong> and are explainable from your choices.</li>
            </ul>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={consented}
                onChange={(e) => setConsented(e.target.checked)}
              />
              <span>I understand this is experimental and consent to continue.</span>
            </label>
          </div>

          <button type="button" className="btn-primary-block" onClick={start} disabled={loading || !consented}>
            {loading ? "Starting…" : "Start journey"}
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    </>
  );
}
