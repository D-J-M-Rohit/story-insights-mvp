import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSession } from "../api";
import { SessionContext } from "../App";

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
    <div className="page center">
      <div className="card">
        <h1>Story Insights MVP</h1>
        <p>
          Story Insights is an experimental reflection tool. It is not clinical advice, diagnosis, or a hiring assessment.
        </p>
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
        <label>
          <input
            type="checkbox"
            checked={consented}
            onChange={(e) => setConsented(e.target.checked)}
            style={{ width: "auto", marginRight: 8 }}
          />
          I understand this is experimental and consent to continue.
        </label>
        <button onClick={start} disabled={loading || !consented}>
          {loading ? "Starting..." : "Start"}
        </button>
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
