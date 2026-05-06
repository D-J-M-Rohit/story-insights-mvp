import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getReport } from "../api";

export default function ReportViewer() {
  const { sessionId } = useParams();
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

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

  return (
    <div className="page">
      <div className="card">
        <h2>Behavioral Insight Report</h2>
        <p>{report.summary}</p>
      </div>

      <div className="card">
        <h3>Feature Scores</h3>
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
      <Link className="button-link" to="/">
        Start another session
      </Link>
    </div>
  );
}
