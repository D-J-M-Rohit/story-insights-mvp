import { useContext, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BarChart3, GitBranch, ShieldCheck } from "lucide-react";
import { login as loginApi, register as registerApi } from "../api";
import { SessionContext } from "../App";
import BrandLogo from "./BrandLogo";

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
      <div className="auth-layout">
        <div className="auth-hero">
          <BrandLogo size="lg" showText />
          <h1>Branching stories for behavioral insight</h1>
          <p className="auth-hero-lead">
            Explore decision patterns through adaptive scenarios and explainable reports.
          </p>
          <div className="auth-pills">
            <span className="pill">
              <GitBranch size={16} aria-hidden />
              Adaptive story
            </span>
            <span className="pill">
              <BarChart3 size={16} aria-hidden />
              Deterministic scoring
            </span>
            <span className="pill">
              <ShieldCheck size={16} aria-hidden />
              Privacy-aware
            </span>
          </div>
          <p className="auth-disclaimer">
            Experimental reflection only. Not clinical, diagnostic, or hiring advice.
          </p>
        </div>

        <div className="card auth-card">
          <h2>{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="muted small">Sign in to continue your sessions and reports.</p>
          <form onSubmit={onSubmit}>
            <label>
              Email
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            </label>
            <button type="submit" className="btn-primary-block" disabled={loading}>
              {loading ? "Please wait…" : mode === "login" ? "Log in" : "Register"}
            </button>
          </form>
          <button
            type="button"
            className="ghost-btn"
            onClick={() => setMode(mode === "login" ? "register" : "login")}
            disabled={loading}
          >
            {mode === "login" ? "Need an account? Register" : "Already have an account? Log in"}
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      </div>
    </div>
  );
}
