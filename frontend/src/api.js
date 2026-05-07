const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers, credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = res.status === 429 ? "Too many requests. Please try again in a moment." : body.detail || "request_failed";
    const err = new Error(message);
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export function createSession(config) {
  return request("/api/v1/sessions", { method: "POST", body: JSON.stringify(config) });
}

export function getSession(sessionId) {
  return request(`/api/v1/sessions/${sessionId}`);
}

export function getSessionState(sessionId) {
  return request(`/api/v1/sessions/${sessionId}/state`);
}

export function getNextScene(payload) {
  return request("/api/v1/scenes/next", { method: "POST", body: JSON.stringify(payload) });
}

export function getReport(sessionId) {
  return request(`/api/v1/reports/${sessionId}`);
}

export function register(email, password) {
  return request("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
}

export function login(email, password) {
  return request("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}

export function logout() {
  return request("/api/v1/auth/logout", { method: "POST" });
}

export function getMe() {
  return request("/api/v1/me");
}

export function getMySessions() {
  return request("/api/v1/my-sessions");
}

export function getScenarioPacks() {
  return request("/api/v1/scenario-packs");
}

export async function downloadReportPdf(sessionId) {
  const res = await fetch(`${BASE_URL}/api/v1/reports/${sessionId}/pdf`, { credentials: "include" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "pdf_download_failed");
  }
  return res.blob();
}

export function submitFeedback(payload) {
  return request("/api/v1/feedback", { method: "POST", body: JSON.stringify(payload) });
}

export function getMyFeedback(sessionId) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return request(`/api/v1/feedback/my${qs}`);
}

export function getFeedbackSummary(sessionId) {
  return request(`/api/v1/feedback/summary?session_id=${encodeURIComponent(sessionId)}`);
}

export function adminListFeedback(status = "flagged") {
  return request(`/api/v1/admin/feedback?status=${encodeURIComponent(status)}`);
}

export function adminReviewFeedback(feedbackId, payload) {
  return request(`/api/v1/admin/feedback/${feedbackId}`, { method: "PATCH", body: JSON.stringify(payload) });
}
