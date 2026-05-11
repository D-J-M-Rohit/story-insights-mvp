import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { login as loginApi, register as registerApi } from "../api";
import { SessionContext } from "../App";

export default function AuthScreen() {
  const navigate = useNavigate();
  const { login } = useContext(SessionContext);
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function onSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const fn = mode === "login" ? loginApi : registerApi;
      const result = await fn(email, password);
      login(result.user);
      navigate("/dashboard");
    } catch (err) {
      setError(err.message || "auth_failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page center">
      <div className="card auth-card">
        <h1>Story Insights</h1>
        <p className="muted">Sign in to continue your sessions and reports.</p>
        <form onSubmit={onSubmit}>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          <button type="submit" disabled={loading}>
            {loading ? "Please wait..." : mode === "login" ? "Login" : "Register"}
          </button>
        </form>
        <button className="ghost-btn" onClick={() => setMode(mode === "login" ? "register" : "login")} disabled={loading}>
          {mode === "login" ? "Need an account? Register" : "Already have an account? Login"}
        </button>
        {error && <p className="error">{error}</p>}
      </div>
    </div>
  );
}
