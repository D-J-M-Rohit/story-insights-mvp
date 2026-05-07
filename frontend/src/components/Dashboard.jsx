import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getMySessions } from "../api";
import { SessionContext } from "../App";

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, setSession, logout } = useContext(SessionContext);
  const [sessions, setSessions] = useState([]);
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
        <p className="muted">
          Review consent and scenario settings before starting a new assessment.
        </p>
        <button onClick={() => {
          setSession(null);
          navigate("/consent");
        }}>
          Start new session
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
            {s.status === "active" && (
              <button className="inline-btn" onClick={() => navigate(`/assessment/${s.id}`)}>
                Resume
              </button>
            )}
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
