import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSession, getMySessions } from "../api";
import { SessionContext } from "../App";

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, setSession, logout } = useContext(SessionContext);
  const [scenario, setScenario] = useState("workplace");
  const [maxTurns, setMaxTurns] = useState(20);
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadSessions() {
      try {
        setSessions(await getMySessions());
      } catch (e) {
        setError(e.message);
      }
    }
    loadSessions();
  }, []);

  async function start() {
    setLoading(true);
    setError("");
    try {
      const session = await createSession({ scenario, max_turns: Number(maxTurns) });
      setSession(session);
      navigate("/assessment");
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <div className="row-between">
        <h2>Dashboard</h2>
        <div>
          <span className="muted">{user?.email}</span>
          <button className="inline-btn" onClick={logout}>
            Logout
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Start New Session</h3>
        <label>
          Scenario
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            <option value="workplace">workplace</option>
            <option value="school">school</option>
            <option value="emergency">emergency</option>
          </select>
        </label>
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
        <button onClick={start} disabled={loading}>
          {loading ? "Starting..." : "Start new session"}
        </button>
      </div>

      <div className="card">
        <h3>Previous Sessions</h3>
        {sessions.length === 0 && <p className="muted">No sessions yet.</p>}
        {sessions.map((s) => (
          <div key={s.id} className="session-row">
            <div>
              <strong>{s.scenario}</strong>
              <p className="muted small">{new Date(s.created_at).toLocaleString()} · {s.status}</p>
            </div>
            {s.status === "complete" && (
              <button className="inline-btn" onClick={() => navigate(`/report/${s.id}`)}>
                View report
              </button>
            )}
          </div>
        ))}
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
