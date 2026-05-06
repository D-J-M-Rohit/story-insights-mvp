# story-insights-mvp

A minimalist full-stack MVP for a branching-story behavioral-insight app. Users complete timed scene choices, telemetry is recorded, and a backend scoring engine computes experimental insight features.

## What This MVP Does

- Starts an assessment session with scenario and max turns.
- Generates scene-by-scene branching choices (mock/OpenAI/Gemini via backend).
- Captures telemetry: latency, hover log, hover switch count, changed intent, timeout.
- Stores sessions/scenes/choices/reports in SQLite.
- Computes 10 backend-scored features (LLM does not score users).
- Displays report with Recharts bar + radar visualizations.

## Architecture Summary

- Frontend: React + Vite web app (`frontend/`)
  - Consent/start screen
  - Assessment flow
  - Scene renderer + timer bar
  - Report viewer with charts
- Backend: FastAPI service (`backend/`)
  - Session/scenes/report endpoints
  - LLM provider abstraction (`mock`, `openai`, `gemini`)
  - Strict prompt builder
  - SQLite data store
  - Explicit scoring engine

## Install

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Run

- Open [http://localhost:5173](http://localhost:5173)
- Backend health: [http://localhost:8000/health](http://localhost:8000/health)

## Environment Setup

Configure `backend/.env`.

### Mock mode (no keys required)

```env
LLM_PROVIDER=mock
```

### OpenAI mode

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_key
OPENAI_MODEL=your_model
```

### Gemini mode

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_key
GEMINI_MODEL=gemini-2.5-flash
```

If OpenAI/Gemini fails or returns malformed JSON, backend gracefully falls back to mock scene generation.

## API Endpoints

- `POST /api/v1/sessions`
- `POST /api/v1/scenes/next`
- `GET /api/v1/reports/{session_id}`
- `GET /health`

## Notes

- LLM generates scenes/options only.
- Scoring is computed exclusively by backend formulas.
- This MVP report is experimental and should not be treated as a clinical or hiring assessment.

## TODO Next Steps

- TODO: Add authentication and role separation (no JWT yet in MVP).
- TODO: Add production database migration path (Postgres later, SQLite for MVP).
- TODO: Add async job queue and caching layers (Redis later).
- TODO: Add vector retrieval and document ingestion (FAISS/S3/PDF export later).
- TODO: Add deployment orchestration (Kubernetes later).
