import { useContext, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { downloadReportPdf, getReport } from "../api";
import { SessionContext } from "../App";
import FeedbackCard from "./FeedbackCard";

function formatDate(value) {
  if (value == null || value === "") return "-";
  try {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString();
  } catch {
    return String(value);
  }
}

function formatDuration(ms) {
  if (ms == null || Number.isNaN(Number(ms))) return "-";
  const sec = Number(ms) / 1000;
  return `${sec.toFixed(1)} sec`;
}

function formatScore(value) {
  if (value == null || value === "") return "—";
  const n = Number(value);
  if (Number.isNaN(n)) return String(value);
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

function compactLabelList(traitBuckets) {
  if (!Array.isArray(traitBuckets) || traitBuckets.length === 0) return "";
  const labels = traitBuckets
    .map((tb) => (tb && typeof tb.label === "string" ? tb.label.trim() : ""))
    .filter(Boolean);
  const unique = [...new Set(labels)];
  const limited = unique.slice(0, 6);
  return limited.join(" · ");
}

function featureMetaLine(f) {
  const parts = [];
  if (f.raw_score != null) parts.push(`Raw: ${formatScore(f.raw_score)}`);
  if (f.evidence_count != null) parts.push(`Evidence: ${f.evidence_count}`);
  if (f.interpretation_status != null && String(f.interpretation_status).trim() !== "") {
    parts.push(String(f.interpretation_status));
  }
  return parts.length > 0 ? parts.join(" · ") : null;
}

/** Remove product-phase wording if present in API copy (e.g. cached reports). */
function stripMvpFromCopy(text) {
  if (text == null || typeof text !== "string") return "";
  return text
    .replace(/\bMVP\b/gi, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([,.])/g, "$1")
    .trim();
}

const REPORT_DISCLAIMER_FALLBACK =
  "This report is experimental and should not be treated as a clinical, hiring, or diagnostic assessment. " +
  "Scores are descriptive signals from a short branching-story session and should be interpreted with the evidence count and confidence band.";

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

  const features = Array.isArray(report.features) ? report.features : [];
  const penList = Array.isArray(report.pen) ? report.pen : [];
  const choices = Array.isArray(report.choices) ? report.choices : [];
  const evidenceCards = Array.isArray(report.evidence_cards) ? report.evidence_cards : [];
  const interpretation = report.interpretation && typeof report.interpretation === "object" ? report.interpretation : {};
  const traitBuckets = Array.isArray(interpretation.trait_buckets) ? interpretation.trait_buckets : [];
  const keySignals = compactLabelList(traitBuckets);

  const penData = penList.map((p) => ({
    metric: p.key ? p.key.replace(/_proxy$/, "") : (p.name || "").split("/")[0].trim() || "—",
    score: p.score,
  }));

  const coverage = choices.reduce((acc, choice) => {
    const target = choice?.scene_metadata?.target_construct;
    if (target) acc[target] = (acc[target] || 0) + 1;
    return acc;
  }, {});

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
          <button type="button" className="inline-btn" onClick={() => navigate("/dashboard")}>
            Dashboard
          </button>
          <button type="button" className="inline-btn" onClick={logout}>
            Logout
          </button>
        </div>
      </div>

      {/* A. Header / report metadata */}
      <div className="card">
        <h2>Behavioral Insight Report</h2>
        <p className="muted">{report.scenario != null ? report.scenario : "—"}</p>
        <p className="muted small">Started: {formatDate(report.started_at)}</p>
        <p className="muted small">Completed: {formatDate(report.completed_at)}</p>
        <p className="muted small">Duration: {formatDuration(report.duration_ms)}</p>
        <p className="muted">
          {stripMvpFromCopy(report.summary) || REPORT_DISCLAIMER_FALLBACK}
        </p>
      </div>

      {/* B. Insights Summary */}
      <div className="card">
        <h3>Insights Summary</h3>
        {interpretation.decision_style != null && interpretation.decision_style !== "" && (
          <p>
            <strong>Decision Style:</strong> {interpretation.decision_style}
          </p>
        )}
        {interpretation.strengths != null && interpretation.strengths !== "" && (
          <p>
            <strong>Strengths in this setting:</strong> {interpretation.strengths}
          </p>
        )}
        {interpretation.growth_areas != null && interpretation.growth_areas !== "" && (
          <p>
            <strong>Possible Growth Area:</strong> {interpretation.growth_areas}
          </p>
        )}
        {interpretation.setting_specific_summary != null && interpretation.setting_specific_summary !== "" && (
          <p>
            <strong>Setting-Specific Summary:</strong> {interpretation.setting_specific_summary}
          </p>
        )}
        {keySignals ? (
          <p className="muted small compact-signals">
            <strong>Key signals:</strong> {keySignals}
          </p>
        ) : null}
      </div>

      {/* C. Construct Coverage */}
      {Object.keys(coverage).length > 0 && (
        <div className="card">
          <h3>Construct Coverage</h3>
          <p className="muted small">
            {["risk", "social", "empathy", "decisiveness", "emotional_regulation"]
              .map((k) => `${k}: ${coverage[k] || 0}`)
              .join(" · ")}
          </p>
        </div>
      )}

      {/* D. Technical Feature Scores */}
      {features.length > 0 && (
        <div className="card">
          <h3>Technical Feature Scores</h3>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={features}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="key" hide />
              <YAxis domain={[0, 100]} />
              <Tooltip />
              <Bar dataKey="score" fill="#4f46e5" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* E. Why this score? evidence cards */}
      {evidenceCards.length > 0 && (
        <div className="card">
          <h3>Why this score?</h3>
          {import.meta.env.DEV && <p className="muted small">Evidence cards: {evidenceCards.length}</p>}
          {evidenceCards.map((card) => (
            <details key={card.feature_key || card.feature_name} className="evidence-card">
              <summary>
                {card.feature_name} - {formatScore(card.score)} <span className="bucket-pill">{card.bucket}</span>
              </summary>
              <p className="muted small">{card.label}</p>
              <p className="muted small">
                {`Reference band: ${Number(card.low_threshold ?? card.reference_low ?? 35)}–${Number(card.high_threshold ?? card.reference_high ?? 65)}. Internal reference only; not a clinical, population, or hiring norm.`}
              </p>
              <ul className="evidence-list">
                {(Array.isArray(card.evidence) ? card.evidence : []).map((e, idx) => (
                  <li key={`${card.feature_key}-${idx}`}>{e}</li>
                ))}
              </ul>
            </details>
          ))}
        </div>
      )}

      {/* F. PEN Proxies radar chart */}
      <div className="card">
        <h3>PEN Proxies</h3>
        <p className="muted small report-section-note">
          These are experimental proxy signals, not clinical personality scores.
        </p>
        {penData.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <RadarChart data={penData}>
              <PolarGrid />
              <PolarAngleAxis dataKey="metric" />
              <Tooltip />
              <Radar dataKey="score" stroke="#0f766e" fill="#14b8a6" fillOpacity={0.5} />
            </RadarChart>
          </ResponsiveContainer>
        ) : (
          <p className="muted small">No PEN proxy data in this report.</p>
        )}
      </div>

      {/* G. Per-feature detail grid */}
      {features.length > 0 && (
        <div className="grid">
          {features.map((f) => {
            const meta = featureMetaLine(f);
            return (
              <div key={f.key || f.name} className="card">
                <h4>{f.name}</h4>
                <strong>{formatScore(f.score)}</strong>
                
                {/* {f.label != null && f.label !== "" && <p className="muted small">Label: {f.label}</p>} */}
                {/* {f.confidence_low != null && f.confidence_high != null && (
                  <p className="confidence-range">
                    Confidence band: {formatScore(f.confidence_low)} – {formatScore(f.confidence_high)}
                  </p>
                )} */}
                {/* {meta ? <p className="muted small feature-meta">{meta}</p> : null} */}

                {f.description != null && f.description !== "" && <p>{f.description}</p>}
              </div>
            );
          })}
        </div>
      )} 
      

      {/* H. PDF download */}
      <button type="button" onClick={onDownloadPdf} disabled={downloading}>
        {downloading ? "Preparing PDF..." : "Download PDF"}
      </button>

      {/* I. FeedbackCard */}
      <FeedbackCard sessionId={sessionId} reportId={report.session_id || sessionId} />

      {/* J. Back to dashboard */}
      <Link className="button-link" to="/dashboard">
        Back to dashboard
      </Link>
    </div>
  );
}
