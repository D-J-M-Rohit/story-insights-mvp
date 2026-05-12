import { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Briefcase, GraduationCap, PlayCircle, Siren } from "lucide-react";
import { getMySessions } from "../api";
import { SessionContext } from "../App";
import AppHeader from "./AppHeader";

function scenarioIcon(scenario) {
  const s = String(scenario || "").toLowerCase();
  if (s === "school") return <GraduationCap size={20} aria-hidden />;
  if (s === "emergency") return <Siren size={20} aria-hidden />;
  return <Briefcase size={20} aria-hidden />;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const { user, setSession } = useContext(SessionContext);
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
    <>
      <AppHeader title="Dashboard" />
      <div className="page">
        <div className="dashboard-hero card">
          <h1>Welcome back</h1>
          <p className="muted">{user?.email}</p>
        </div>

        <div className="card cta-card">
          <h3>Start a new session</h3>
          <p className="muted">
            Review consent and scenario settings before starting a new assessment journey.
          </p>
          <button
            type="button"
            onClick={() => {
              setSession(null);
              navigate("/consent");
            }}
          >
            <span className="scenario-inline">
              <PlayCircle size={20} aria-hidden />
              Start new session
            </span>
          </button>
        </div>

        <div className="card">
          <h3>Previous sessions</h3>
          {sessions.length === 0 && <p className="muted">No sessions yet.</p>}
          {sessions.length > 0 && (
            <div className="session-table">
              {sessions.map((s) => (
                <div key={s.id} className="session-row">
                  <div>
                    <div className="scenario-inline">
                      {scenarioIcon(s.scenario)}
                      <strong>{s.scenario}</strong>
                    </div>
                    <p className="muted small">{new Date(s.created_at).toLocaleString()}</p>
                    <span className={`status-pill status-pill--${s.status === "complete" ? "complete" : "active"}`}>
                      {s.status}
                      {s.status === "active" ? " — in progress" : ""}
                    </span>
                  </div>
                  <div>
                    {s.status === "active" && (
                      <button type="button" className="inline-btn" onClick={() => navigate(`/assessment/${s.id}`)}>
                        Resume
                      </button>
                    )}
                    {s.status === "complete" && (
                      <button type="button" className="inline-btn" onClick={() => navigate(`/report/${s.id}`)}>
                        View report
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        {error && <p className="error">{error}</p>}
      </div>
    </>
  );
}
