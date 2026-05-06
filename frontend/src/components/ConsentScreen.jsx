import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createSession } from "../api";
import { SessionContext } from "../App";

export default function ConsentScreen() {
  const [scenario, setScenario] = useState("workplace");
  const [maxTurns, setMaxTurns] = useState(20);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { setSession } = useContext(SessionContext);

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
    <div className="page center">
      <div className="card">
        <h1>Story Insights MVP</h1>
        <p>Experimental branching-story assessment. Not clinical advice.</p>
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
          {loading ? "Starting..." : "Start"}
        </button>
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
