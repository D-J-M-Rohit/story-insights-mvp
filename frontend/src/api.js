const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const TOKEN_KEY = "story_insights_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}, requireAuth = true) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (requireAuth && getToken()) {
    headers.Authorization = `Bearer ${getToken()}`;
  }
  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });
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
  return request("/api/v1/sessions", { method: "POST", body: JSON.stringify(config) }, true);
}

export function getNextScene(payload) {
  return request("/api/v1/scenes/next", { method: "POST", body: JSON.stringify(payload) }, true);
}

export function getReport(sessionId) {
  return request(`/api/v1/reports/${sessionId}`, {}, true);
}

export function register(email, password) {
  return request("/api/v1/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }, false);
}

export function login(email, password) {
  return request("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }, false);
}

export function getMe() {
  return request("/api/v1/me", {}, true);
}

export function getMySessions() {
  return request("/api/v1/my-sessions", {}, true);
}

export function getScenarioPacks() {
  return request("/api/v1/scenario-packs", {}, true);
}

export async function downloadReportPdf(sessionId) {
  const headers = {};
  if (getToken()) headers.Authorization = `Bearer ${getToken()}`;
  const res = await fetch(`${BASE_URL}/api/v1/reports/${sessionId}/pdf`, { headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "pdf_download_failed");
  }
  return res.blob();
}

export function submitFeedback(payload) {
  return request("/api/v1/feedback", { method: "POST", body: JSON.stringify(payload) }, true);
}

export function getMyFeedback(sessionId) {
  const qs = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return request(`/api/v1/feedback/my${qs}`, {}, true);
}

export function getFeedbackSummary(sessionId) {
  return request(`/api/v1/feedback/summary?session_id=${encodeURIComponent(sessionId)}`, {}, true);
}

export function adminListFeedback(status = "flagged") {
  return request(`/api/v1/admin/feedback?status=${encodeURIComponent(status)}`, {}, true);
}

export function adminReviewFeedback(feedbackId, payload) {
  return request(`/api/v1/admin/feedback/${feedbackId}`, { method: "PATCH", body: JSON.stringify(payload) }, true);
}
