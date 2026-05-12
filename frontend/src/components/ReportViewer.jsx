import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { BarChart3, BrainCircuit, Clock, Download, FileText, Sparkles } from "lucide-react";
import { downloadReportPdf, getReport } from "../api";
import AppHeader from "./AppHeader";
import BrandLogo from "./BrandLogo";
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

function signalPillsFromTraitBuckets(traitBuckets) {
  if (!Array.isArray(traitBuckets) || traitBuckets.length === 0) return [];
  const labels = traitBuckets
    .map((tb) => (tb && typeof tb.label === "string" ? tb.label.trim() : ""))
    .filter(Boolean);
  return [...new Set(labels)].slice(0, 8);
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

function strongestFeatureName(features) {
  if (!Array.isArray(features) || features.length === 0) return null;
  const sorted = [...features].sort((a, b) => (Number(b.score) || 0) - (Number(a.score) || 0));
  return sorted[0]?.name || null;
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

const COVERAGE_KEYS = ["risk", "social", "empathy", "decisiveness", "emotional_regulation"];

export default function ReportViewer() {
  const { sessionId } = useParams();
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

  if (error) {
    return (
      <>
        <AppHeader title="Report" />
        <div className="page center error">{error}</div>
      </>
    );
  }
  if (!report) {
    return (
      <>
        <AppHeader title="Report" />
        <div className="page center app-loading" role="status">
          Loading report…
        </div>
      </>
    );
  }

  const features = Array.isArray(report.features) ? report.features : [];
  const penList = Array.isArray(report.pen) ? report.pen : [];
  const choices = Array.isArray(report.choices) ? report.choices : [];
  const evidenceCards = Array.isArray(report.evidence_cards) ? report.evidence_cards : [];
  const benchmarkRows = Array.isArray(report.benchmark_comparisons) ? report.benchmark_comparisons : [];
  const interpretation = report.interpretation && typeof report.interpretation === "object" ? report.interpretation : {};
  const traitBuckets = Array.isArray(interpretation.trait_buckets) ? interpretation.trait_buckets : [];
  const keySignals = compactLabelList(traitBuckets);
  const signalPills = signalPillsFromTraitBuckets(traitBuckets);
  const topFeatureName = strongestFeatureName(features);

  const penData = penList.map((p) => ({
    metric: p.key ? p.key.replace(/_proxy$/, "") : (p.name || "").split("/")[0].trim() || "—",
    score: p.score,
  }));

  const coverage = choices.reduce((acc, choice) => {
    const target = choice?.scene_metadata?.target_construct;
    if (target) acc[target] = (acc[target] || 0) + 1;
    return acc;
  }, {});

  const coverageMax = Math.max(1, ...COVERAGE_KEYS.map((k) => coverage[k] || 0));

  async function onDownloadPdf() {
    setDownloading(true);
    try {
      const blob = await downloadReportPdf(sessionId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `psychometric-insights-report-${sessionId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e.message);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <>
      <AppHeader title="Report" />
      <div className="page">
        <div className="card report-hero">
          <div className="row-between" style={{ alignItems: "flex-start" }}>
            <BrandLogo size="sm" showText />
          </div>
          <h2 style={{ margin: "12px 0 8px" }}>Behavioral insight report</h2>
          <div className="report-hero-meta">
            <span className="meta-pill">
              <FileText size={14} aria-hidden style={{ verticalAlign: "middle", marginRight: 4 }} />
              Scenario: {report.scenario != null ? report.scenario : "—"}
            </span>
            <span className="meta-pill">
              <Clock size={14} aria-hidden style={{ verticalAlign: "middle", marginRight: 4 }} />
              Duration: {formatDuration(report.duration_ms)}
            </span>
            <span className="meta-pill">Completed: {formatDate(report.completed_at)}</span>
            {topFeatureName ? (
              <span className="meta-pill" title="Highest numeric score among reported features">
                Strongest signal: {topFeatureName}
              </span>
            ) : null}
          </div>
          <p className="muted" style={{ marginBottom: 0 }}>
            {stripMvpFromCopy(report.summary) || REPORT_DISCLAIMER_FALLBACK}
          </p>
        </div>

        <div className="card insights-premium">
          <h3>
            <BrainCircuit size={22} aria-hidden />
            Decision style summary
          </h3>
          {interpretation.decision_style != null && interpretation.decision_style !== "" && (
            <p>
              <strong>Decision style:</strong> {interpretation.decision_style}
            </p>
          )}
          {interpretation.strengths != null && interpretation.strengths !== "" && (
            <p>
              <strong>Strengths in this setting:</strong> {interpretation.strengths}
            </p>
          )}
          {interpretation.growth_areas != null && interpretation.growth_areas !== "" && (
            <p>
              <strong>Possible growth area:</strong> {interpretation.growth_areas}
            </p>
          )}
          {interpretation.setting_specific_summary != null && interpretation.setting_specific_summary !== "" && (
            <p>
              <strong>Setting-specific summary:</strong> {interpretation.setting_specific_summary}
            </p>
          )}
          {signalPills.length > 0 ? (
            <div className="signal-pills" aria-label="Key signals">
              {signalPills.map((label) => (
                <span key={label} className="signal-pill">
                  <Sparkles size={12} aria-hidden style={{ marginRight: 4, verticalAlign: "middle" }} />
                  {label}
                </span>
              ))}
            </div>
          ) : keySignals ? (
            <p className="muted small compact-signals">
              <strong>Key signals:</strong> {keySignals}
            </p>
          ) : null}
        </div>

        {Object.keys(coverage).length > 0 && (
          <div className="card">
            <h3>Construct coverage</h3>
            <p className="muted small">Counts of scenes targeting each construct in this session.</p>
            <div className="coverage-bars">
              {COVERAGE_KEYS.map((k) => {
                const n = coverage[k] || 0;
                const pct = Math.round((n / coverageMax) * 100);
                return (
                  <div key={k} className="coverage-row">
                    <span>{k}</span>
                    <div className="coverage-track" title={`${n} scenes`}>
                      <div className="coverage-fill" style={{ width: `${pct}%` }} />
                    </div>
                    <span aria-label={`${k} count`}>{n}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {features.length > 0 && (
          <div className="card">
            <h3>Technical feature scores</h3>
            <p className="chart-hint">
              <BarChart3 size={16} aria-hidden style={{ verticalAlign: "text-bottom", marginRight: 6 }} />
              Bars show backend-computed scores (0–100). Open evidence cards below for how each score was formed.
            </p>
            <ResponsiveContainer width="100%" height={320}>
              <BarChart data={features}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis dataKey="key" hide />
                <YAxis domain={[0, 100]} tick={{ fill: "#64748b" }} />
                <Tooltip />
                <Bar dataKey="score" fill="#4f46e5" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {evidenceCards.length > 0 && (
          <div className="card">
            <h3>Why this score?</h3>
            {import.meta.env.DEV && <p className="muted small">Evidence cards: {evidenceCards.length}</p>}
            {evidenceCards.map((card) => (
              <details key={card.feature_key || card.feature_name} className="evidence-card">
                <summary>
                  {card.feature_name} — {formatScore(card.score)}{" "}
                  <span className="bucket-pill">{card.bucket}</span>
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

        {benchmarkRows.length > 0 && (
          <div className="card">
            <h3>Benchmark comparisons</h3>
            <p className="muted small">Each row compares your score to an internal reference band (not a population norm).</p>
            <div className="benchmark-list">
              {benchmarkRows.map((row) => (
                <div key={row.feature_key || row.metric_name} className="benchmark-item">
                  <div>
                    <p className="benchmark-title">{row.metric_name || row.feature_key}</p>
                    <p className="muted small" style={{ margin: 0 }}>
                      Reference {row.low_threshold ?? 35}–{row.high_threshold ?? 65}
                    </p>
                  </div>
                  <div className="benchmark-right">
                    <strong>{formatScore(row.score)}</strong>
                    <div>
                      <span className="benchmark-band">{row.band || "within reference band"}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="card">
          <h3>PEN proxies</h3>
          <p className="muted small report-section-note">Experimental proxy signals, not clinical personality scores.</p>
          {penData.length > 0 ? (
            <ResponsiveContainer width="100%" height={320}>
              <RadarChart data={penData}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="metric" tick={{ fill: "#475569", fontSize: 12 }} />
                <Tooltip />
                <Radar dataKey="score" stroke="#0f766e" fill="#14b8a6" fillOpacity={0.45} />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <p className="muted small">No PEN proxy data in this report.</p>
          )}
        </div>

        {features.length > 0 && (
          <div className="grid">
            {features.map((f) => {
              const meta = featureMetaLine(f);
              const scoreNum = Math.min(100, Math.max(0, Number(f.score) || 0));
              return (
                <div key={f.key || f.name} className="card derived-feature-card">
                  <h4 style={{ marginTop: 0 }}>{f.name}</h4>
                  <strong style={{ fontSize: "1.35rem" }}>{formatScore(f.score)}</strong>
                  {f.label != null && f.label !== "" && <p className="muted small">Label: {f.label}</p>}
                  <div className="feature-score-bar" aria-hidden>
                    <div className="feature-score-bar-fill" style={{ width: `${scoreNum}%` }} />
                  </div>
                  {f.confidence_low != null && f.confidence_high != null && (
                    <p className="confidence-range">
                      Confidence band: {formatScore(f.confidence_low)} – {formatScore(f.confidence_high)}
                    </p>
                  )}
                  {f.confidence_low != null && f.confidence_high != null && (
                    <span className="confidence-pill">
                      Band {formatScore(f.confidence_low)}–{formatScore(f.confidence_high)}
                    </span>
                  )}
                  {meta ? <p className="muted small feature-meta">{meta}</p> : null}
                  {f.description != null && f.description !== "" && <p>{f.description}</p>}
                </div>
              );
            })}
          </div>
        )}

        <button type="button" className="no-print" onClick={onDownloadPdf} disabled={downloading}>
          <span className="scenario-inline">
            <Download size={18} aria-hidden />
            {downloading ? "Preparing PDF…" : "Download PDF"}
          </span>
        </button>

        <div className="no-print">
          <FeedbackCard sessionId={sessionId} reportId={report.session_id || sessionId} />
        </div>

        <Link className="button-link no-print" to="/dashboard">
          Back to dashboard
        </Link>
      </div>
    </>
  );
}
