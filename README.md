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
