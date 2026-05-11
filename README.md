# Story Insights

Production-style platform for branching story insights with:
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
2. Dashboard
3. Consent and scenario selection
4. Start assessment (`/assessment/{session_id}`)
5. Complete assessment
6. View report
7. Download PDF

### Resume assessment

- The UI uses `/assessment/{session_id}` so a refresh reloads server state via `GET /api/v1/sessions/{session_id}/state` (owner-checked).
- The latest **unanswered** scene is restored when present; otherwise the client requests the next scene as usual (no duplicate scene creation from the resume endpoint).
- If the session is already complete, the client redirects to `/report/{session_id}`.

### Micro-feedback idempotency

- In-session micro-feedback is limited server-side to **one stored event per user, session, and turn**; repeats return `{"status": "duplicate_ignored", "existing_id": "..."}` without a second row.
- An optional `Idempotency-Key` header deduplicates feedback POSTs per user (in-memory).

### Auth response modes

- With `AUTH_COOKIE_ENABLED=true` and `AUTH_RETURN_TOKEN_IN_BODY=false` (default), `POST /api/v1/auth/register` and `POST /api/v1/auth/login` return `token_type: "cookie"` and **omit** `access_token` from JSON while still setting the HttpOnly cookie.
- For scripts and tests, use `?include_token=true` or request header `X-Return-Bearer-Token: true` (when `AUTH_ALLOW_TOKEN_RESPONSE_OVERRIDE=true`) to receive `access_token` in the body.

### Optional provider smoke tests

Skipped unless enabled explicitly:

```bash
cd backend
RUN_PROVIDER_SMOKE_TESTS=true LLM_PROVIDER=openai OPENAI_API_KEY=your_key pytest tests/test_provider_smoke_optional.py -k openai
RUN_PROVIDER_SMOKE_TESTS=true LLM_PROVIDER=gemini GEMINI_API_KEY=your_key pytest tests/test_provider_smoke_optional.py -k gemini
```

### Privacy scrubbing

- Shared `privacy_scrub` pattern rules redact emails, phones, URLs, bearer/JWT-like strings, API-key-shaped text, database URLs, IPs, SSN-like patterns, and long numeric IDs in logs and nested trace payloads (key-based redaction still applies).

### Retrieval fallback observability

- Retrieval can record a low-cardinality **`retrieval_fallback_reason`** (for example `disabled`, `no_query`, `no_results`, `index_missing`, `faiss_error`, `embedding_error`) on context traces and, when `BENCHMARK_DEBUG_FIELDS_ENABLED=true`, under `debug` on scene responses alongside `retrieval_fallback_used`.
- Prometheus counter: **`story_insights_retrieval_fallback_total`** with labels `backend` and `reason` only (no user/session/query text).
- Failures degrade to **no retrieval context**; story generation and **scoring** continue unchanged.

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
AUTH_COOKIE_ENABLED=true
AUTH_COOKIE_NAME=access_token
AUTH_COOKIE_SECURE=false
AUTH_COOKIE_SAMESITE=lax
AUTH_COOKIE_MAX_AGE_MINUTES=10080
AUTH_RETURN_TOKEN_IN_BODY=false
AUTH_ALLOW_TOKEN_RESPONSE_OVERRIDE=true

CORS_ORIGINS=http://localhost:5173

REPORT_LLM_SUMMARY_ENABLED=true
```

Cookie auth notes:
- Browser auth uses an HttpOnly cookie by default when `AUTH_COOKIE_ENABLED=true`.
- By default (`AUTH_RETURN_TOKEN_IN_BODY=false`) login/register JSON does **not** include `access_token`; use `?include_token=true` or `X-Return-Bearer-Token: true` for bearer in the body.
- Bearer auth remains supported for scripts/tests.
- JWT storage in browser `localStorage` was removed for security.
- In production, set `AUTH_COOKIE_SECURE=true` and serve over HTTPS.

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
- `GET /api/v1/sessions/{session_id}`
- `GET /api/v1/sessions/{session_id}/state`
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
- Confidence bands are exploratory estimates for short sessions (often around 5 turns). UI language uses estimated range / directional confidence, not validated clinical intervals.
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

- Backend tests are necessary because this platform combines auth, scene generation, telemetry, deterministic scoring, and report pipelines; one successful UI run does not validate scoring/report correctness.
- `pytest` + FastAPI `TestClient` are used for backend tests, and `pytest monkeypatch` is used to force mock provider behavior and test env overrides.
- Provider health endpoints exist because `mock`, `openai`, and `gemini` are interchangeable behind the gateway; ops needs a quick view of active provider, fallback rate, and latency quality.
- Metrics exist because averages hide long-tail slowness. The platform now emits Prometheus-compatible counters/histograms for request/error rates and latency distributions.
- Structured JSON logs are privacy-preserving operational metadata only: route/method/status/timing/request_id/trace_id/provider/error metadata; no passwords, tokens, API keys, raw emails, prompts, scene bodies, report bodies, or full telemetry payloads.
- W3C-style `traceparent` is parsed when present. Correlation headers are emitted as `X-Request-ID` and `traceparent`.
- This project does not include a full OpenTelemetry collector, Grafana dashboards, or SIEM plumbing yet; those are future production steps.

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

Provider circuit status endpoint:

- `GET http://localhost:8000/api/v1/provider/circuit-status` (admin)
- Returns circuit state (`closed`/`open`/`half_open`) and failure counters.
- Does not expose API keys, tokens, prompts, or raw secrets.

Future production direction:

- Scrape `/metrics` with Prometheus.
- Visualize service health in Grafana.
- Propagate correlation IDs through API gateway/load balancer.
- Add full OpenTelemetry collector later.
- Keep raw prompt/response details only in restricted trace stores when needed, not general logs.

## Feedback Service

- Feedback is optional and privacy-first.
- Feedback improves UX, story pacing, and clarity tuning, but does not affect scores.
- Feedback does not affect deterministic scoring, derived features, evidence cards, or confidence bands.
- Micro-feedback can produce short-lived presentation hints (pace/clarity/tone/variety) only.
- Feedback hints never change target construct, difficulty progression, construct coverage, or validation thresholds.
- Raw comments are retained for 90 days by default, then purged via admin endpoint.
- Aggregate feedback rollups may be retained for 365 days.
- Raw feedback comments are not logged in structured logs.
- Micro-feedback appears at most once per session (frontend local session marker).

## Analysis NLP Service

- The platform includes a lightweight deterministic analysis service for feedback/comment text.
- It performs:
  - text normalization and preprocessing
  - NER-style PII redaction with regex/rule patterns
  - controlled topic tagging from comment text and tags
  - optional sentiment labeling for product-experience feedback
- It does not call OpenAI/Gemini or any external LLM.
- It does not use heavy NLP model pipelines in this implementation.
- It does not affect scoring, CDI, ADQ, PEN proxies, confidence bands, or benchmark comparisons.
- Sentiment/topic outputs are UX/quality signals only and are not clinical, diagnostic, or hiring conclusions.

Architecture note:
- In this implementation, the Analysis and Reports layer focuses on telemetry normalization, deterministic scoring, evidence mapping, benchmark comparison, report interpretation, and lightweight feedback/comment analysis.
- Standalone advanced sentiment, named-entity recognition, and topic modeling remain future extensions and are not core scoring inputs.

Endpoints:
- `POST /api/v1/feedback`
- `GET /api/v1/feedback/my?session_id=...`
- `GET /api/v1/feedback/summary?session_id=...`
- `GET /api/v1/admin/feedback?status=flagged`
- `PATCH /api/v1/admin/feedback/{feedback_id}`
- `POST /api/v1/admin/feedback/rollup`
- `POST /api/v1/admin/feedback/purge-old`

Submit post-report feedback:

```bash
curl -X POST "http://localhost:8000/api/v1/feedback" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"<session_id>",
    "report_id":"<session_id>",
    "feedback_type":"session",
    "channel":"post_report",
    "category":"story_report_experience",
    "rating_useful":4,
    "rating_engaging":4,
    "tags":["helpful","clear"],
    "comment":"The report was clear and practical.",
    "consent_comment":true
  }'
```

Submit in-session micro feedback:

```bash
curl -X POST "http://localhost:8000/api/v1/feedback" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id":"<session_id>",
    "scene_id":"<scene_id>",
    "turn":2,
    "feedback_type":"micro",
    "channel":"in_session",
    "category":"pacing_clarity",
    "tags":["too_fast","confusing"]
  }'
```

Admin review flagged feedback:

```bash
curl "http://localhost:8000/api/v1/admin/feedback?status=flagged" \
  -H "Authorization: Bearer <admin_token>"

curl -X PATCH "http://localhost:8000/api/v1/admin/feedback/<feedback_id>" \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"moderation_status":"resolved","reviewer_note":"triaged"}'
```

## Benchmarks, Retrieval, FAISS, and Object Storage

- Retrieval is optional and disabled by default (`RETRIEVAL_ENABLED=false`).
- Retrieval improves narrative continuity/context only.
- Retrieval does not affect scoring, derived features, confidence bands, or evidence cards.
- PostgreSQL/SQLite stores fragment metadata + embeddings as the system of record.
- FAISS is an optional local ANN index built from `fragment_embeddings`.
- Exact retrieval can be used before FAISS (`RETRIEVAL_BACKEND=exact`).
- Object storage is optional and used for archival artifacts.
- PDF streaming remains the default report download behavior.
- Archived PDFs are disabled by default (`ARCHIVE_PDFS_ENABLED=false`).
- Buckets should remain private; signed URLs are short-lived.

Install backend deps:

```bash
cd backend
pip install -r requirements.txt
```

Seed embeddings:

```bash
python -m app.scripts.seed_embeddings --scenario-pack default
```

Rebuild FAISS:

```bash
python -m app.scripts.rebuild_faiss --index default --scenario-pack default
```

Benchmark scene generation:

```bash
BASE_URL=http://localhost:8000 N=50 python -m app.scripts.bench_scene_generation
```

Benchmark embeddings + FAISS:

```bash
MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2 N=100000 python -m app.scripts.bench_embeddings_faiss
```

Benchmark retrieval + generation:

```bash
BASE_URL=http://localhost:8000 N=30 python -m app.scripts.bench_retrieval_generation
```

Object storage options:
- `filesystem` backend works locally by default.
- MinIO/S3 can be enabled via `OBJECT_STORAGE_BACKEND` + endpoint/credential env vars.

Retention defaults:
- traces: 30 days
- prompts: 30 days
- PDFs: 7 days (archiving disabled by default)
- FAISS snapshots: 14 days

Security notes:
- do not expose raw prompt/trace archives to participants
- keep object storage keys private
- secrets are not logged

Future migration note:
- pgvector, Weaviate, Pinecone, Redis queues, and Kubernetes remain future options and are not part of this implementation.
