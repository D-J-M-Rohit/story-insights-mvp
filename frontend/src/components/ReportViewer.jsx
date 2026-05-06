import { useContext, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { downloadReportPdf, getReport } from "../api";
import { SessionContext } from "../App";

export default function ReportViewer() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { logout } = useContext(SessionContext);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setReport(await getReport(sessionId));
      } catch (e) {
        setError(e.message);
      }
    }
    load();
  }, [sessionId]);

  if (error) return <div className="page center error">{error}</div>;
  if (!report) return <div className="page center">Loading report...</div>;

  const penData = report.pen.map((p) => ({
    metric: p.key ? p.key.replace(/_proxy$/, "") : p.name.split("/")[0].trim(),
    score: p.score,
  }));
  const interpretation = report.interpretation || {};

  async function onDownloadPdf() {
    setDownloading(true);
    try {
      const blob = await downloadReportPdf(sessionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `story-insights-report-${sessionId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="page">
      <div className="row-between">
        <h2>Report</h2>
        <div>
          <button className="inline-btn" onClick={() => navigate("/dashboard")}>
            Dashboard
          </button>
          <button className="inline-btn" onClick={logout}>
            Logout
          </button>
        </div>
      </div>
      <div className="card">
        <h2>Behavioral Insight Report</h2>
        <p className="muted">{report.scenario}</p>
        <p className="muted">
          Experimental reflection only. This is not a clinical, diagnostic, or hiring assessment.
        </p>
        <p>{report.summary}</p>
      </div>
      <div className="card">
        <h3>Friendly Interpretation</h3>
        <p><strong>Decision Style:</strong> {interpretation.decision_style}</p>
        <p><strong>Strengths in this setting:</strong> {interpretation.strengths}</p>
        <p><strong>Possible Growth Area:</strong> {interpretation.growth_areas}</p>
        <p><strong>Setting-Specific Summary:</strong> {interpretation.setting_specific_summary}</p>
      </div>
      <div className="grid">
        {(interpretation.trait_buckets || []).map((tb) => (
          <div key={tb.key} className="card">
            <h4>{tb.key}</h4>
            <strong>{tb.score}</strong>
            <p>{tb.label}</p>
            <p className="muted small">{tb.bucket}</p>
          </div>
        ))}
      </div>

      <div className="card">
        <h3>Technical Feature Scores</h3>
        <ResponsiveContainer width="100%" height={320}>
          <BarChart data={report.features}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="key" hide />
            <YAxis domain={[0, 100]} />
            <Tooltip />
            <Bar dataKey="score" fill="#4f46e5" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="card">
        <h3>PEN Proxies</h3>
        <ResponsiveContainer width="100%" height={320}>
          <RadarChart data={penData}>
            <PolarGrid />
            <PolarAngleAxis dataKey="metric" />
            <Tooltip />
            <Radar dataKey="score" stroke="#0f766e" fill="#14b8a6" fillOpacity={0.5} />
          </RadarChart>
        </ResponsiveContainer>
      </div>

      <div className="grid">
        {report.features.map((f) => (
          <div key={f.key} className="card">
            <h4>{f.name}</h4>
            <strong>{f.score}</strong>
            {f.raw_score != null && (
              <p className="muted small">
                Raw: {f.raw_score} · Evidence: {f.evidence_count} · {f.interpretation_status}
              </p>
            )}
            {f.confidence_low != null && f.confidence_high != null && (
              <p className="muted small">
                Confidence band: {f.confidence_low} – {f.confidence_high}
              </p>
            )}
            <p>{f.description}</p>
          </div>
        ))}
      </div>
      <button onClick={onDownloadPdf} disabled={downloading}>
        {downloading ? "Preparing PDF..." : "Download PDF"}
      </button>
      <Link className="button-link" to="/dashboard">Back to dashboard</Link>
    </div>
  );
}
