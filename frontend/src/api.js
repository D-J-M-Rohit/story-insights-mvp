const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const err = new Error(body.detail || "request_failed");
    err.status = res.status;
    throw err;
  }
  return res.json();
}

export function createSession(config) {
  return request("/api/v1/sessions", { method: "POST", body: JSON.stringify(config) });
}

export function getNextScene(payload) {
  return request("/api/v1/scenes/next", { method: "POST", body: JSON.stringify(payload) });
}

export function getReport(sessionId) {
  return request(`/api/v1/reports/${sessionId}`);
}
