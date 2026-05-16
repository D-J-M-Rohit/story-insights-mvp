# Scenario-Based Psychometric Insights with GenAI Narration

A production-style behavioral assessment platform that places users inside branching story scenarios and derives psychometric insights from their choices. The platform combines deterministic scoring, optional LLM-driven scene generation, privacy-preserving telemetry, and on-demand PDF report generation.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Prerequisites](#3-prerequisites)
4. [Repository Layout](#4-repository-layout)
5. [Quick Start (Local)](#5-quick-start-local)
6. [Environment Variables Reference](#6-environment-variables-reference)
7. [Database Setup](#7-database-setup)
8. [LLM Configuration](#8-llm-configuration)
9. [PDF Generation](#9-pdf-generation)
10. [User Flow](#10-user-flow)
11. [API Reference](#11-api-reference)
12. [Scenario Packs & Prompt Policy Engine](#12-scenario-packs--prompt-policy-engine)
13. [Scoring, Evidence & Confidence](#13-scoring-evidence--confidence)
14. [Telemetry & Feedback](#14-telemetry--feedback)
15. [Retrieval / RAG (Optional)](#15-retrieval--rag-optional)
16. [Object Storage & Archival](#16-object-storage--archival)
17. [Observability](#17-observability)
18. [Rate Limiting](#18-rate-limiting)
19. [Security](#19-security)
20. [Testing](#20-testing)
21. [Utility Scripts](#21-utility-scripts)
22. [Production Checklist](#22-production-checklist)

---

## 1. Project Overview

**Story Insights** presents users with short branching story scenes across three scenario domains:

| Pack | Domain |
|------|---------|
| `workplace_core_v1` | Workplace decision-making |
| `school_core_v1` | Academic/school context |
| `emergency_core_v1` | High-pressure emergency situations |

Each scenario session runs 5–10 turns. After the final turn the backend scores choices deterministically against construct definitions (CDI, ADQ, PEN proxies) and generates a structured report. An optional LLM summary layer paraphrases the findings. Reports can be downloaded as polished PDFs.

**Key design decisions:**

- Scoring is **always deterministic and backend-owned**; the LLM never changes scores.
- Auth uses **HttpOnly cookies** by default (no JWT in `localStorage`).
- All telemetry is **privacy-scrubbed** before logging or storage.
- The platform runs entirely **without API keys** in mock mode.

---

## 2. Architecture

```
┌─────────────────────────────────────┐
│           Browser / Frontend        │
│  React 18 + Vite + react-router-dom │
│  http://localhost:5173              │
└──────────────┬──────────────────────┘
               │ HTTP (cookie auth)
┌──────────────▼──────────────────────┐
│           Backend API               │
│  FastAPI + Uvicorn                  │
│  http://localhost:8000              │
│                                     │
│  ┌──────────┐  ┌─────────────────┐  │
│  │ Auth/JWT │  │ Prompt Policy   │  │
│  ├──────────┤  ├─────────────────┤  │
│  │ Scoring  │  │ LLM Gateway     │  │
│  ├──────────┤  │  (mock/openai)  │  │
│  │ Reports  │  ├─────────────────┤  │
│  ├──────────┤  │ Context Builder │  │
│  │ PDF Gen  │  │  (RAG optional) │  │
│  └──────────┘  └─────────────────┘  │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│  PostgreSQL 16                      │
│  (Docker / Neon / Supabase / local) │
└─────────────────────────────────────┘
```

---

## 3. Prerequisites

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 18+ | Frontend build |
| npm | 9+ | Frontend deps |
| Docker (optional) | 24+ | Local Postgres |
| OpenAI API key (optional) | — | LLM scene generation |

> Without Docker, point `DATABASE_URL` at any accessible PostgreSQL 14+ instance.

---

## 4. Repository Layout

```
story-insights-mvp/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── analysis_nlp.py          # Lightweight NLP: PII redaction, tagging, sentiment
│   │   ├── archive_service.py       # Archival to object storage
│   │   ├── auth.py                  # JWT + cookie auth
│   │   ├── benchmark_baselines.py   # Baseline data
│   │   ├── benchmarks.py            # Benchmark comparison engine
│   │   ├── circuit_breaker.py       # Provider circuit breaker
│   │   ├── confidence.py            # Confidence band estimation
│   │   ├── config.py                # Settings (pydantic-settings)
│   │   ├── context_builder.py       # RAG context assembly
│   │   ├── context_trace.py         # Context builder audit trace
│   │   ├── database.py              # DB engine + session factory
│   │   ├── embeddings.py            # Sentence-transformer wrapper
│   │   ├── evaluation_graphs.py     # Formula-based scoring graph data
│   │   ├── evidence_mapper.py       # Evidence cards per construct
│   │   ├── feedback.py              # Feedback service
│   │   ├── generation_trace.py      # Per-scene generation audit trace
│   │   ├── llm_gateway.py           # Mock + OpenAI provider abstraction
│   │   ├── logging_config.py        # Structured JSON logging
│   │   ├── main.py                  # FastAPI app + middleware wiring
│   │   ├── metrics.py               # Prometheus counters/histograms
│   │   ├── models.py                # SQLAlchemy ORM models
│   │   ├── object_store.py          # Object storage abstraction (fs/S3/MinIO)
│   │   ├── pdf_report.py            # PDF orchestration (Playwright/ReportLab)
│   │   ├── pdf_template.py          # ReportLab fallback builder
│   │   ├── policy_trace.py          # Policy input/output audit trace
│   │   ├── privacy_scrub.py         # Log/trace sanitization patterns
│   │   ├── prompt_policy.py         # Policy engine (construct/difficulty/knobs)
│   │   ├── prompts.py               # Prompt builders
│   │   ├── provider_health.py       # Provider health window tracking
│   │   ├── rate_limit.py            # Token-bucket rate limiter
│   │   ├── report_interpreter.py    # Score → human-readable buckets
│   │   ├── request_context.py       # Request-scoped context vars
│   │   ├── retention.py             # Data retention enforcement
│   │   ├── retrieval.py             # Fragment retrieval router
│   │   ├── retrieval_store.py       # PostgreSQL fragment + embedding store
│   │   ├── scenario_packs.py        # Scenario pack loader
│   │   ├── scene_validation.py      # Scene output validation
│   │   ├── schemas.py               # Pydantic request/response schemas
│   │   ├── scoring.py               # Deterministic scoring engine
│   │   ├── security_headers.py      # HTTP security headers middleware
│   │   ├── store.py                 # Session/scene CRUD
│   │   ├── telemetry.py             # Telemetry ingestion + normalization
│   │   ├── trace_utils.py           # W3C traceparent parsing
│   │   ├── scenario_packs_data/     # JSON pack definitions
│   │   │   ├── emergency_core_v1.json
│   │   │   ├── school_core_v1.json
│   │   │   └── workplace_core_v1.json
│   │   ├── templates/
│   │   │   └── report_print.html    # Jinja2 template for Playwright PDF
│   │   └── scripts/
│   │       ├── __init__.py
│   │       ├── bench_embeddings_faiss.py
│   │       ├── bench_retrieval_generation.py
│   │       ├── bench_scene_generation.py
│   │       ├── generate_db_observed_graphs.py
│   │       ├── generate_metric_simulation_graphs.py
│   │       ├── rebuild_faiss.py
│   │       └── seed_embeddings.py
│   ├── tests/
│   │   ├── conftest.py
│   │   ├── test_analysis_nlp.py
│   │   ├── test_auth.py
│   │   ├── test_auth_cookie_response.py
│   │   ├── test_benchmark_baselines.py
│   │   ├── test_benchmarks.py
│   │   ├── test_circuit_breaker.py
│   │   ├── test_confidence.py
│   │   ├── test_context_builder.py
│   │   ├── test_cookie_auth.py
│   │   ├── test_derived_features.py
│   │   ├── test_evaluation_graphs.py
│   │   ├── test_evidence_mapper.py
│   │   ├── test_feedback.py
│   │   ├── test_feedback_idempotency.py
│   │   ├── test_generation_trace.py
│   │   ├── test_health.py
│   │   ├── test_metrics.py
│   │   ├── test_object_store.py
│   │   ├── test_pdf_report.py
│   │   ├── test_policy_context_generation_flow.py
│   │   ├── test_privacy_logs.py
│   │   ├── test_privacy_scrub.py
│   │   ├── test_prompt_policy.py
│   │   ├── test_provider_circuit_status.py
│   │   ├── test_provider_health.py
│   │   ├── test_provider_smoke_optional.py
│   │   ├── test_rate_limit.py
│   │   ├── test_reports.py
│   │   ├── test_retrieval.py
│   │   ├── test_retrieval_fallback_diagnostics.py
│   │   ├── test_retrieval_store.py
│   │   ├── test_scenario_packs.py
│   │   ├── test_scene_validation.py
│   │   ├── test_scoring.py
│   │   ├── test_security_headers.py
│   │   ├── test_session_duration.py
│   │   ├── test_session_resume.py
│   │   ├── test_sessions.py
│   │   ├── test_telemetry.py
│   │   └── test_trace_utils.py
│   ├── data/
│   │   ├── archive/                 # Local object archive root
│   │   └── faiss/
│   │       ├── build/               # FAISS index build workspace
│   │       └── current/             # Active FAISS index
│   ├── generated_graphs/            # PNG output from graph scripts
│   ├── .env                         # Local secrets (gitignored)
│   ├── .env.example                 # Copy to .env and edit
│   ├── pytest.ini
│   ├── requirements.txt
│   └── story_insights.db            # SQLite fallback DB (local dev only)
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Router setup
│   │   ├── api.js                   # Fetch API client
│   │   ├── main.jsx                 # React entry point
│   │   ├── styles.css               # Global styles
│   │   └── components/
│   │       ├── AppHeader.jsx
│   │       ├── AssessmentFlow.jsx
│   │       ├── AssessmentSessionRoute.jsx
│   │       ├── AuthScreen.jsx
│   │       ├── BrandLogo.jsx
│   │       ├── ConsentScreen.jsx
│   │       ├── Dashboard.jsx
│   │       ├── FeedbackCard.jsx
│   │       ├── MicroFeedbackPrompt.jsx
│   │       ├── ReportViewer.jsx
│   │       ├── SceneLoading.jsx
│   │       ├── SceneRenderer.jsx
│   │       └── TimerBar.jsx
│   ├── dist/                        # Production build output
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── vite.config.js
├── .gitignore
├── docker-compose.yml               # Postgres 16 service
└── README.md
```

---

## 5. Quick Start (Local)

### Step 1 — Clone and enter the repo

```bash
git clone <your-repo-url> story-insights-mvp
cd story-insights-mvp
```

### Step 2 — Start Postgres (Docker)

```bash
docker compose up -d postgres
```

This starts PostgreSQL 16 at `localhost:5432` with credentials `postgres/postgres` and database `story_insights`.

> Skip this step if you have an existing Postgres instance. Update `DATABASE_URL` in step 4 accordingly.

### Step 3 — Set up the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Step 4 — Configure environment

```bash
cp .env.example .env
```

Open `backend/.env` and adjust at minimum:

```env
LLM_PROVIDER=mock                  # Use 'openai' for real scene generation
OPENAI_API_KEY=                    # Required only when LLM_PROVIDER=openai
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/story_insights
JWT_SECRET_KEY=change-me-in-production
```

### Step 5 — Install Chromium for PDF generation

```bash
# Still inside backend venv
python -m playwright install chromium
```

> Required for `PDF_RENDERER=playwright` (default). If skipped, set `PDF_FALLBACK_REPORTLAB=true` in `.env` to use the plain ReportLab renderer instead.

### Step 6 — Start the backend

```bash
uvicorn app.main:app --reload --port 8000
```

The backend creates all database tables automatically on first start via SQLAlchemy `create_all`.

### Step 7 — Set up and start the frontend

```bash
cd ../frontend
npm install
npm run dev
```

### Step 8 — Open the app

Navigate to [http://localhost:5173](http://localhost:5173).

---

## 6. Environment Variables Reference

All variables live in `backend/.env` (copy from `backend/.env.example`).

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `mock` | `mock` or `openai` |
| `OPENAI_API_KEY` | _(empty)_ | Required when `LLM_PROVIDER=openai` |
| `OPENAI_MODEL` | `gpt-4.1-mini` | OpenAI model name |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/story_insights` | SQLAlchemy connection string |

### Auth & JWT

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | `change-me-in-production` | HMAC signing key — **change this** |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `10080` | Token lifetime (7 days) |
| `AUTH_COOKIE_ENABLED` | `true` | Set HttpOnly cookie on login/register |
| `AUTH_COOKIE_NAME` | `access_token` | Cookie name |
| `AUTH_COOKIE_SECURE` | `false` | Set `true` in production (HTTPS) |
| `AUTH_COOKIE_SAMESITE` | `lax` | SameSite policy |
| `AUTH_COOKIE_MAX_AGE_MINUTES` | `10080` | Cookie max-age |
| `AUTH_RETURN_TOKEN_IN_BODY` | `false` | Include `access_token` in JSON response |
| `AUTH_ALLOW_TOKEN_RESPONSE_OVERRIDE` | `true` | Allow `?include_token=true` override |

### CORS

| Variable | Default | Description |
|----------|---------|-------------|
| `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed origins |

### Reports & PDF

| Variable | Default | Description |
|----------|---------|-------------|
| `REPORT_LLM_SUMMARY_ENABLED` | `true` | Enable LLM paraphrase in reports |
| `PDF_RENDERER` | `playwright` | `playwright` or `reportlab` |
| `PDF_FALLBACK_REPORTLAB` | `true` | Fall back to ReportLab if Playwright fails |
| `PDF_INCLUDE_DEBUG` | `false` | Include debug fields in PDF |
| `PDF_PAGE_SIZE` | `A4` | Page size |
| `PDF_MARGIN_TOP/RIGHT/BOTTOM/LEFT` | `14mm/12mm/14mm/12mm` | PDF margins |

### Logging & Metrics

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Python log level |
| `LOG_FORMAT` | `json` | `json` or `text` |
| `LOG_SALT` | `change-me-for-user-hashing` | Salt for hashing user IDs in logs |
| `METRICS_ENABLED` | `true` | Expose `/metrics` (Prometheus format) |
| `PROVIDER_HEALTH_WINDOW` | `50` | Rolling window for provider health tracking |
| `SLOW_SCENE_GENERATION_MS` | `3000` | Threshold for slow generation warnings |

### Feedback & NLP Analysis

| Variable | Default | Description |
|----------|---------|-------------|
| `FEEDBACK_ENABLED` | `true` | Enable feedback endpoints |
| `FEEDBACK_COMMENT_MAX_CHARS` | `300` | Max feedback comment length |
| `FEEDBACK_RAW_RETENTION_DAYS` | `90` | Days before raw comment purge |
| `FEEDBACK_AGGREGATE_RETENTION_DAYS` | `365` | Days to retain rollup data |
| `FEEDBACK_MICRO_PROMPT_ENABLED` | `true` | Show micro-feedback prompt in-session |
| `FEEDBACK_MICRO_PROMPT_TURN` | `2` | Turn number to show micro-feedback |
| `ANALYSIS_NLP_ENABLED` | `true` | Enable NLP analysis on feedback |
| `ANALYSIS_SENTIMENT_ENABLED` | `true` | Sentiment labeling |
| `ANALYSIS_TOPIC_TAGS_ENABLED` | `true` | Topic extraction |
| `ANALYSIS_PII_REDACTION_ENABLED` | `true` | Regex-based PII redaction |
| `ANALYSIS_COMMENT_MAX_CHARS` | `300` | Max chars passed to NLP |

### Retrieval / RAG (disabled by default)

| Variable | Default | Description |
|----------|---------|-------------|
| `RETRIEVAL_ENABLED` | `false` | Enable retrieval context |
| `RETRIEVAL_BACKEND` | `none` | `none`, `exact`, or `faiss_hnsw` |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | HuggingFace model |
| `EMBEDDING_DEVICE` | `cpu` | `cpu` or `cuda` |
| `FAISS_INDEX_DIR` | `./data/faiss` | FAISS index directory |
| `RETRIEVAL_TOP_K` | `10` | Top-K fragments to retrieve |

### Object Storage (disabled by default)

| Variable | Default | Description |
|----------|---------|-------------|
| `OBJECT_ARCHIVE_ENABLED` | `false` | Enable archival to object storage |
| `OBJECT_STORAGE_BACKEND` | `filesystem` | `filesystem`, `s3`, or `minio` |
| `OBJECT_STORAGE_BUCKET` | `story-insights` | Bucket/container name |
| `OBJECT_STORAGE_ENDPOINT` | _(empty)_ | S3/MinIO endpoint URL |
| `OBJECT_STORAGE_ACCESS_KEY` | _(empty)_ | Access key |
| `OBJECT_STORAGE_SECRET_KEY` | _(empty)_ | Secret key |
| `ARCHIVE_PDFS_ENABLED` | `false` | Archive generated PDFs |
| `ARCHIVE_TRACE_RETENTION_DAYS` | `30` | Trace archive retention |
| `ARCHIVE_PROMPT_RETENTION_DAYS` | `30` | Prompt archive retention |
| `ARCHIVE_PDF_RETENTION_DAYS` | `7` | PDF archive retention |

### Security & Circuit Breaker

| Variable | Default | Description |
|----------|---------|-------------|
| `SECURITY_HEADERS_ENABLED` | `true` | Add security headers to responses |
| `CSP_CONNECT_SRC` | `http://localhost:8000 http://localhost:5173` | CSP connect-src value |
| `PROVIDER_CIRCUIT_BREAKER_ENABLED` | `true` | Enable LLM provider circuit breaker |
| `PROVIDER_CIRCUIT_FAILURE_THRESHOLD` | `5` | Failures before opening circuit |
| `PROVIDER_CIRCUIT_FAILURE_WINDOW_SEC` | `30` | Window for failure counting |
| `PROVIDER_CIRCUIT_OPEN_SEC` | `60` | Duration circuit stays open |
| `BENCHMARK_COMPARISONS_ENABLED` | `true` | Enable benchmark comparison layer |
| `BENCHMARK_DEBUG_FIELDS_ENABLED` | `true` | Include debug fields in benchmark responses |

---

## 7. Database Setup

### Local via Docker

```bash
docker compose up -d postgres
```

Postgres 16 starts at `localhost:5432`. Tables are created automatically when the backend starts for the first time.

### Cloud (Neon / Supabase / Railway)

1. Create a PostgreSQL database on your chosen provider.
2. Copy the connection string.
3. Set it in `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>/<dbname>?sslmode=require
```

4. Restart the backend.

### SQLite (for minimal/CI use)

```env
DATABASE_URL=sqlite+aiosqlite:///./story_insights.db
```

---

## 8. LLM Configuration

### Mock mode (no API key required)

```env
LLM_PROVIDER=mock
```

All scenes are generated from deterministic templates. Suitable for development and testing.

### OpenAI mode

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
```

If OpenAI scene generation fails, the backend automatically falls back to mock scenes. If LLM report summarization fails, the backend falls back to deterministic interpretation text.

### Circuit breaker

When `PROVIDER_CIRCUIT_BREAKER_ENABLED=true`, repeated provider failures open the circuit for `PROVIDER_CIRCUIT_OPEN_SEC` seconds, preventing request pile-up. Status is visible at `GET /api/v1/provider/circuit-status`.

---

## 9. PDF Generation

PDF reports are generated on-demand and streamed directly to the browser — nothing is stored by default.

### Playwright (default, recommended)

Renders the `report_print.html` Jinja2 template through Chromium headlessly, producing a polished print-quality PDF.

**Setup:**
```bash
cd backend
source .venv/bin/activate
python -m playwright install chromium
```

**Config:**
```env
PDF_RENDERER=playwright
PDF_FALLBACK_REPORTLAB=true   # Fall back gracefully if Chromium is missing
```

### ReportLab (plain fallback)

A simpler plain-text PDF built with the ReportLab library. Reliable in CI or minimal environments where Chromium cannot be installed.

```env
PDF_RENDERER=reportlab
```

---

## 10. User Flow

```
Register / Login
      │
      ▼
Dashboard  (lists past sessions)
      │
      ▼
Consent Screen + Scenario Selection
      │
      ▼
Assessment  /assessment/{session_id}
  ┌── Scene rendered (story situation)
  │   User picks from 3–4 choices
  │   Telemetry captured (dwell time, focus, intent changes)
  └── Repeat for each turn (5–10 scenes)
      │
      ▼
Report  /report/{session_id}
  • Construct scores + interpretation buckets
  • Evidence cards explaining each score
  • Confidence bands (exploratory, not clinical)
  • Benchmark comparison
  • Optional LLM narrative summary
  • Download PDF button
```

### Session resume

Navigating to `/assessment/{session_id}` after a browser refresh calls `GET /api/v1/sessions/{session_id}/state`, which restores the latest unanswered scene. Completed sessions redirect to `/report/{session_id}`.

### Auth modes

- **Browser (default):** HttpOnly cookie — no `access_token` in JSON body.
- **Scripts/tests:** Append `?include_token=true` or send `X-Return-Bearer-Token: true` header (requires `AUTH_ALLOW_TOKEN_RESPONSE_OVERRIDE=true`).

---

## 11. API Reference

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/auth/register` | Register new user |
| `POST` | `/api/v1/auth/login` | Login |
| `GET` | `/api/v1/me` | Current user info |

### Sessions

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/sessions` | Create new assessment session |
| `GET` | `/api/v1/sessions/{session_id}` | Get session details |
| `GET` | `/api/v1/sessions/{session_id}/state` | Resume state (latest unanswered scene) |
| `GET` | `/api/v1/my-sessions` | List user's sessions |

### Scenes

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/scenes/next` | Submit choice, advance to next scene |

### Reports

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/reports/{session_id}` | Get full report JSON |
| `GET` | `/api/v1/reports/{session_id}/pdf` | Download PDF (streamed) |
| `GET` | `/api/v1/reports/{session_id}/evidence` | Evidence cards per construct |
| `GET` | `/api/v1/reports/{session_id}/derived-features` | Per-metric derived feature rows |
| `GET` | `/api/v1/reports/{session_id}/confidence` | Confidence band estimates |

### Feedback

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/feedback` | Submit post-report or micro feedback |
| `GET` | `/api/v1/feedback/my` | List own feedback (`?session_id=...`) |
| `GET` | `/api/v1/feedback/summary` | Aggregated feedback summary |

### Admin (Feedback)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/admin/feedback` | List feedback (`?status=flagged`) |
| `PATCH` | `/api/v1/admin/feedback/{feedback_id}` | Update moderation status |
| `POST` | `/api/v1/admin/feedback/rollup` | Run aggregation rollup |
| `POST` | `/api/v1/admin/feedback/purge-old` | Purge old raw comments |

### Scenario Packs & Policy

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/scenario-packs` | List available scenario packs |
| `POST` | `/api/v1/policy/preview` | Preview policy decision for a session turn |
| `GET` | `/api/v1/policy-traces/{session_id}` | Policy audit traces |

### Debug / Traces

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/debug/sessions/{session_id}/traces` | Generation traces (`?kind=generation`) |
| `GET` | `/api/v1/debug/scenes/{scene_id}/generation-trace` | Single scene trace |
| `GET` | `/api/v1/context-traces/{session_id}` | Context builder audit traces |
| `POST` | `/api/v1/context/preview` | Preview context assembly |

### Provider & Health

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/provider/status` | Active provider, fallback rate, latency |
| `GET` | `/api/v1/provider/circuit-status` | Circuit breaker state and failure counts |
| `GET` | `/metrics` | Prometheus metrics |
| `GET` | `/health` | Health check (exempt from rate limiting) |

---

## 12. Scenario Packs & Prompt Policy Engine

Scenario packs are JSON files in `backend/app/scenario_packs_data/`. Each pack defines:

- **Constructs** to assess (e.g., decision quality, stress tolerance)
- **Construct minimums** — how many turns must cover each construct
- **Difficulty curve** — how challenge escalates across turns
- **Safety bounds** — rejected scene content categories
- **Reusable fragments** — narrative building blocks for the context builder

The **Prompt Policy Engine** (`prompt_policy.py`) selects a target construct and scene knobs before every generation call. The LLM generates scenes only within policy constraints. Policy decisions are stored in `PolicyTrace` rows for auditability.

Built-in packs:

```
workplace_core_v1   School workplace decisions
school_core_v1      Academic pressure & integrity
emergency_core_v1   High-stakes emergency response
```

---

## 13. Scoring, Evidence & Confidence

### Deterministic scoring

`scoring.py` converts raw choice sequences into normalized construct scores (0–100). Scores are never modified by LLM output.

### Evidence cards

`evidence_mapper.py` maps each score to a set of behavioral evidence items explaining what choices contributed to the score. Evidence is surfaced in the report and in `GET /api/v1/reports/{session_id}/evidence`.

### Derived features

`DerivedFeatures` stores per-metric rows (score, evidence, confidence metadata, scorer version) separately from the report JSON for auditability and reconstruction. Available at `GET /api/v1/reports/{session_id}/derived-features`.

### Confidence bands

`confidence.py` computes exploratory confidence ranges for short sessions (typically 5 turns). The UI displays estimated ranges with directional language, not validated clinical intervals.

---

## 14. Telemetry & Feedback

### Behavioral telemetry

Captured during assessment without collecting raw pointer coordinates or keystroke timing:

- Dwell time per scene
- Focus loss events
- Hover switching patterns
- Intent-change signals (answer changes before submission)

Telemetry is summarized and bounded before storage. Raw payloads are not logged.

### Feedback service

Users can submit:
- **Post-report feedback** — overall session ratings, free-text comments, tag selections
- **In-session micro-feedback** — pacing/clarity signals (prompted once per session at turn 2)

Micro-feedback is idempotent server-side: one stored event per user/session/turn. Duplicate submissions return `{"status": "duplicate_ignored"}`.

**Submit post-report feedback:**

```bash
curl -X POST "http://localhost:8000/api/v1/feedback" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "<session_id>",
    "report_id": "<session_id>",
    "feedback_type": "session",
    "channel": "post_report",
    "category": "story_report_experience",
    "rating_useful": 4,
    "rating_engaging": 4,
    "tags": ["helpful", "clear"],
    "comment": "The report was clear and practical.",
    "consent_comment": true
  }'
```

**Submit micro-feedback:**

```bash
curl -X POST "http://localhost:8000/api/v1/feedback" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "<session_id>",
    "scene_id": "<scene_id>",
    "turn": 2,
    "feedback_type": "micro",
    "channel": "in_session",
    "category": "pacing_clarity",
    "tags": ["too_fast", "confusing"]
  }'
```

### Analysis NLP

`analysis_nlp.py` runs on feedback text without calling any external LLM:

- Text normalization
- Regex-based PII redaction (emails, phones, IPs, tokens, URLs)
- Controlled topic tagging
- Optional sentiment labeling

NLP outputs are UX/quality signals only — they do not affect scores.

---

## 15. Retrieval / RAG (Optional)

Retrieval is **disabled by default** (`RETRIEVAL_ENABLED=false`). When enabled it improves narrative continuity — it does not affect scoring.

### Enable exact retrieval

```env
RETRIEVAL_ENABLED=true
RETRIEVAL_BACKEND=exact
```

### Enable FAISS vector retrieval

```env
RETRIEVAL_ENABLED=true
RETRIEVAL_BACKEND=faiss_hnsw
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
FAISS_INDEX_DIR=./data/faiss
```

**Seed fragment embeddings:**

```bash
cd backend
source .venv/bin/activate
python -m app.scripts.seed_embeddings --scenario-pack default
```

**Rebuild FAISS index:**

```bash
python -m app.scripts.rebuild_faiss --index default --scenario-pack default
```

### Retrieval fallback observability

When retrieval fails, the backend degrades gracefully (no retrieval context) and records a `retrieval_fallback_reason` on context traces. Prometheus counter: `story_insights_retrieval_fallback_total{backend, reason}`.

---

## 16. Object Storage & Archival

Archival is **disabled by default** (`OBJECT_ARCHIVE_ENABLED=false`). PDFs are always streamed on demand.

### Local filesystem (default when enabled)

```env
OBJECT_ARCHIVE_ENABLED=true
OBJECT_STORAGE_BACKEND=filesystem
OBJECT_STORAGE_FILESYSTEM_ROOT=./data/archive
```

### S3 / MinIO

```env
OBJECT_STORAGE_BACKEND=s3          # or minio
OBJECT_STORAGE_BUCKET=story-insights
OBJECT_STORAGE_ENDPOINT=https://...
OBJECT_STORAGE_ACCESS_KEY=...
OBJECT_STORAGE_SECRET_KEY=...
```

Retention defaults (when archival is on):

| Artifact | Default retention |
|----------|------------------|
| Generation traces | 30 days |
| Prompt archives | 30 days |
| PDFs | 7 days |
| FAISS snapshots | 14 days |

---

## 17. Observability

### Prometheus metrics

```
GET http://localhost:8000/metrics
```

Emits counters and histograms for request rates, error rates, latency distributions, retrieval fallbacks, and provider health.

### Structured JSON logs

All operational logs are JSON-formatted and include: route, method, status, timing, `request_id`, `traceparent`, provider metadata. Passwords, tokens, API keys, emails, prompts, and scene/report bodies are never logged.

### W3C trace propagation

The backend parses incoming `traceparent` headers and emits `X-Request-ID` and `traceparent` on responses.

### Provider health

```
GET http://localhost:8000/api/v1/provider/status
GET http://localhost:8000/api/v1/provider/circuit-status
```

---

## 18. Rate Limiting

Token-bucket rate limiter (in-memory, suitable for single-instance deployments):

| Route | Rate | Burst |
|-------|------|-------|
| `POST /api/v1/scenes/next` | 10 req/s | 20 |
| `GET /api/v1/reports/*` | 3 req/s | 6 |
| `POST /api/v1/auth/login` | 5 req/min | 5 |
| `GET /api/v1/*` (default) | 30 req/s | 60 |
| `/health` | exempt | — |

> For multi-instance production deployments, move rate limiting to Redis, API Gateway, or Envoy.

---

## 19. Security

- **JWT storage:** removed from `localStorage`; uses HttpOnly cookie by default.
- **Privacy scrubbing:** `privacy_scrub.py` redacts emails, phones, URLs, bearer/JWT tokens, API keys, database URLs, IPs, SSN-like patterns, and long numeric IDs from logs and trace payloads.
- **Security headers:** `security_headers.py` middleware adds `Content-Security-Policy`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, and `Strict-Transport-Security`.
- **Secrets:** never logged, never stored in traces.
- **Object storage:** buckets should be private; signed URLs have a short TTL (`OBJECT_STORAGE_SIGNED_URL_TTL_SEC=300`).

**Production hardening checklist:**

- Set `JWT_SECRET_KEY` to a long random value.
- Set `AUTH_COOKIE_SECURE=true` and serve over HTTPS.
- Set `LOG_SALT` to a unique random value.
- Restrict `CORS_ORIGINS` to your production domain.
- Set `CSP_CONNECT_SRC` to your production API URL.
- Keep `OBJECT_STORAGE_ACCESS_KEY` and `OBJECT_STORAGE_SECRET_KEY` in a secrets manager.

---

## 20. Testing

### Run all backend tests

```bash
cd backend
source .venv/bin/activate
pytest
```

### Run with coverage

```bash
pytest --cov=app --cov-report=term-missing
```

### Test file overview

| File | Area |
|------|------|
| `test_auth.py` | Registration, login, JWT |
| `test_auth_cookie_response.py` | Cookie auth modes |
| `test_cookie_auth.py` | HttpOnly cookie behavior |
| `test_sessions.py` | Session CRUD |
| `test_session_resume.py` | Resume state endpoint |
| `test_scoring.py` | Deterministic scoring |
| `test_reports.py` | Report generation |
| `test_pdf_report.py` | PDF renderer |
| `test_evidence_mapper.py` | Evidence card mapping |
| `test_derived_features.py` | DerivedFeatures rows |
| `test_confidence.py` | Confidence bands |
| `test_prompt_policy.py` | Policy engine |
| `test_context_builder.py` | Context assembly |
| `test_retrieval.py` | Retrieval routing |
| `test_retrieval_store.py` | Fragment store |
| `test_retrieval_fallback_diagnostics.py` | Fallback reasons |
| `test_generation_trace.py` | Generation audit trace |
| `test_scenario_packs.py` | Pack loading |
| `test_scene_validation.py` | Scene output validation |
| `test_feedback.py` | Feedback endpoints |
| `test_feedback_idempotency.py` | Micro-feedback dedup |
| `test_analysis_nlp.py` | NLP analysis |
| `test_telemetry.py` | Telemetry ingestion |
| `test_metrics.py` | Prometheus counters |
| `test_rate_limit.py` | Token bucket limiter |
| `test_circuit_breaker.py` | Provider circuit breaker |
| `test_provider_health.py` | Health window |
| `test_provider_circuit_status.py` | Circuit status endpoint |
| `test_benchmarks.py` | Benchmark comparison |
| `test_benchmark_baselines.py` | Baseline data |
| `test_object_store.py` | Object storage backends |
| `test_privacy_scrub.py` | PII scrubbing patterns |
| `test_privacy_logs.py` | Log sanitization |
| `test_security_headers.py` | HTTP security headers |
| `test_session_duration.py` | Session timing |
| `test_trace_utils.py` | W3C traceparent |
| `test_evaluation_graphs.py` | Graph formula correctness |
| `test_health.py` | Health check endpoint |
| `test_policy_context_generation_flow.py` | End-to-end policy → context → generation |

### Optional provider smoke tests (require API key)

```bash
RUN_PROVIDER_SMOKE_TESTS=true LLM_PROVIDER=openai OPENAI_API_KEY=sk-... \
  pytest tests/test_provider_smoke_optional.py -k openai
```

---

## 21. Utility Scripts

All scripts run from the `backend/` directory with the venv activated.

### Evaluation graphs

Generate PNG scoring simulation graphs into `backend/generated_graphs/`:

```bash
# Formula-based controlled simulations (G1–G4)
python -m app.scripts.generate_metric_simulation_graphs

# DB-observed graphs from completed sessions (DB1–DB4)
python -m app.scripts.generate_db_observed_graphs
```

Optional flags:

```bash
python -m app.scripts.generate_metric_simulation_graphs \
  --output-dir backend/generated_graphs --format png --show false
```

Graphs use the matplotlib `Agg` backend (headless). No user IDs or emails appear in labels.

### Benchmarks

```bash
# Scene generation throughput
BASE_URL=http://localhost:8000 N=50 python -m app.scripts.bench_scene_generation

# Embedding + FAISS indexing throughput
MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2 N=100000 \
  python -m app.scripts.bench_embeddings_faiss

# Retrieval + generation combined latency
BASE_URL=http://localhost:8000 N=30 python -m app.scripts.bench_retrieval_generation
```

### FAISS management

```bash
python -m app.scripts.seed_embeddings --scenario-pack default
python -m app.scripts.rebuild_faiss --index default --scenario-pack default
```

---

## 22. Production Checklist

- [ ] Set `JWT_SECRET_KEY` to a cryptographically random 32+ character string
- [ ] Set `LOG_SALT` to a unique random value
- [ ] Set `AUTH_COOKIE_SECURE=true`
- [ ] Serve over HTTPS (TLS termination at load balancer or reverse proxy)
- [ ] Restrict `CORS_ORIGINS` to your production domain
- [ ] Set `DATABASE_URL` to a production PostgreSQL instance with SSL (`?sslmode=require`)
- [ ] Configure `OBJECT_STORAGE_BACKEND=s3` or `minio` with private bucket and short-TTL signed URLs
- [ ] Set `ARCHIVE_PDFS_ENABLED=false` unless archival is needed
- [ ] Move rate limiting to Redis / API Gateway for multi-instance deployments
- [ ] Set up Prometheus scrape of `/metrics` and Grafana dashboards
- [ ] Add OpenTelemetry collector for distributed tracing
- [ ] Rotate `OPENAI_API_KEY` via a secrets manager; do not commit to source control
- [ ] Review and tighten `CSP_CONNECT_SRC` for your production domains
- [ ] Enable `PROVIDER_CIRCUIT_BREAKER_ENABLED=true` (already default)
- [ ] Run `pytest` CI on every push
