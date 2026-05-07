# Story Insights MVP

Production-style MVP for branching story insights with:
- JWT auth + persistent user sessions
- PostgreSQL-backed storage (local or cloud)
- Deterministic backend scoring
- Friendly interpretation buckets + optional LLM summary
- On-demand PDF report generation (streamed, not stored)

## Setup

1) Install backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

2) Start local Postgres (optional, recommended for local dev):

```bash
docker compose up -d postgres
```

3) Run backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

4) Install frontend:

```bash
cd frontend
npm install
npm run dev
```

5) Open:
- [http://localhost:5173](http://localhost:5173)

## Auth Flow

1. Register
2. Start session
3. Complete assessment
4. View report
5. Download PDF

## Environment

Edit `backend/.env`:

```env
LLM_PROVIDER=mock
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash

DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/story_insights

JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080

CORS_ORIGINS=http://localhost:5173

REPORT_LLM_SUMMARY_ENABLED=true
```

## Cloud Database

- Create PostgreSQL on Neon, Supabase, or Railway.
- Paste the connection string into `DATABASE_URL`.
- Restart backend.

## Local Database

- Run local Postgres or use Docker (`docker compose up -d postgres`).
- Keep `DATABASE_URL` pointed at local DB.

## LLM Behavior

- Scene generation uses `LLM_PROVIDER` (`mock`, `openai`, `gemini`).
- If OpenAI/Gemini scene generation fails, backend falls back safely to mock scenes.
- Report summaries use `REPORT_LLM_SUMMARY_ENABLED=true` and same provider env.
- If report LLM summary fails or returns invalid JSON, backend falls back to deterministic interpretation.

## Key Endpoints

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/me`
- `GET /api/v1/my-sessions`
- `POST /api/v1/sessions`
- `POST /api/v1/scenes/next`
- `GET /api/v1/reports/{session_id}`
- `GET /api/v1/reports/{session_id}/pdf`
- `GET /health`

## Prompt Policy Engine and Scenario Packs

- Scenario Packs define per-scenario assessment blueprints (construct minimums, difficulty curve, safety bounds, and reusable fragments).
- Prompt Policy picks target construct and scene knobs before every generation call.
- LLM generates only within policy constraints; scoring remains deterministic and backend-owned.
- Policy traces are stored for auditability (policy input/output, prompt hash, validation, fallback reason, latency).
- Built-in packs:
  - `workplace_core_v1`
  - `school_core_v1`
  - `emergency_core_v1`

Debugging endpoints:
- `GET /api/v1/scenario-packs`
- `POST /api/v1/policy/preview`
- `GET /api/v1/policy-traces/{session_id}`

Mock mode still works without API keys.

## Context Builder / RAG Preparation

- Context Builder assembles compact story memory before scene generation.
- It retrieves scenario-pack fragments by deterministic tag and difficulty scoring.
- It adds anti-repetition constraints to reduce near-duplicate scene setups.
- It stores `ContextTrace` records for auditability.
- It does not send raw telemetry, auth data, emails, tokens, or passwords to the LLM prompt.
- This is deterministic retrieval-first; vector embeddings/FAISS can be added later.

Debug endpoints:
- `GET /api/v1/context-traces/{session_id}`
- `POST /api/v1/context/preview`

Mock mode continues to work without API keys.

## Generation Traces, Enhanced Telemetry, and Evidence Cards

- Generation traces capture provider/model/status/timing/hash metadata per scene generation.
- Traces support audit/debug and do not drive user scoring.
- Prompt text is not persisted by default; prompt hashes are stored.
- Enhanced telemetry captures dwell time, focus loss, hover switching, and intent-change signals.
- No raw pointer movement coordinates or keystroke timing are collected.
- Evidence cards explain deterministic score outputs with fixed behavioral components.
- LLM summaries may paraphrase evidence but do not change scores/evidence.
- Debug trace responses are sanitized.

Endpoints:
- `GET /api/v1/debug/sessions/{session_id}/traces?kind=generation`
- `GET /api/v1/debug/scenes/{scene_id}/generation-trace`
- `GET /api/v1/reports/{session_id}/evidence`

Privacy notes:
- No passwords/tokens/API keys/raw emails are stored in traces.
- Raw telemetry is bounded and summarized.

## Derived Features, Confidence Bands, and Rate Limiting

- `DerivedFeatures` exists because storing metrics only in `report_json` limits auditability. Per-metric rows preserve score, evidence, confidence metadata, and scorer version for reconstruction.
- Confidence bands are exploratory MVP estimates for short sessions (often around 5 turns). UI language uses estimated range / directional confidence, not validated clinical intervals.
- Rate limiting is applied to expensive routes:
  - `/api/v1/scenes/next`: 10 requests/sec, burst 20
  - `/api/v1/reports/*`: 3 requests/sec, burst 6
  - `/api/v1/auth/login`: 5 requests/minute, burst 5
  - default `/api/v1/*`: 30 requests/sec, burst 60
  - `/health` is exempt
- The current limiter uses in-memory token buckets, suitable for local/demo/single-instance use. Multi-instance production should move the same policies to Redis or API Gateway/Envoy.

Additional endpoints:
- `GET /api/v1/reports/{session_id}/derived-features`
- `GET /api/v1/reports/{session_id}/confidence`

## Testing, Provider Health, Metrics, and Privacy-Preserving Logs

- Backend tests are necessary because this MVP combines auth, scene generation, telemetry, deterministic scoring, and report pipelines; one successful UI run does not validate scoring/report correctness.
- `pytest` + FastAPI `TestClient` are used for backend tests, and `pytest monkeypatch` is used to force mock provider behavior and test env overrides.
- Provider health endpoints exist because `mock`, `openai`, and `gemini` are interchangeable behind the gateway; ops needs a quick view of active provider, fallback rate, and latency quality.
- Metrics exist because averages hide long-tail slowness. The MVP now emits Prometheus-compatible counters/histograms for request/error rates and latency distributions.
- Structured JSON logs are privacy-preserving operational metadata only: route/method/status/timing/request_id/trace_id/provider/error metadata; no passwords, tokens, API keys, raw emails, prompts, scene bodies, report bodies, or full telemetry payloads.
- W3C-style `traceparent` is parsed when present. Correlation headers are emitted as `X-Request-ID` and `traceparent`.
- This MVP does not include a full OpenTelemetry collector, Grafana dashboards, or SIEM plumbing yet; those are future production steps.

Run backend tests:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

Run coverage:

```bash
cd backend
pytest --cov=app --cov-report=term-missing
```

Metrics endpoint:

- `GET http://localhost:8000/metrics`

Provider health endpoint:

- `GET http://localhost:8000/api/v1/provider/status`

Future production direction:

- Scrape `/metrics` with Prometheus.
- Visualize service health in Grafana.
- Propagate correlation IDs through API gateway/load balancer.
- Add full OpenTelemetry collector later.
- Keep raw prompt/response details only in restricted trace stores when needed, not general logs.
