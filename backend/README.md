# Feynman Companion Backend

FastAPI backend for the Feynman companion demo. The conversation runtime uses
LangGraph, JWT authentication, and SQLite-backed session persistence.

Runtime requirement: Python 3.13.

## Run

```bash
cd /Users/chen/Code/Feynman-Companion-AI-Agent
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

## Local Env

`.env.local` is ignored by Git. Copy the example file first:

```bash
cp .env.local.example .env.local
```

Then fill your own DeepSeek API key:

```env
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_CHAT_MODELS=deepseek-flash,deepseek-v4-pro
LLM_PROVIDER=deepseek
REQUEST_TIMEOUT_SECONDS=30
AUTH_SECRET_KEY=replace_with_a_long_random_secret
AUTH_TOKEN_EXPIRE_MINUTES=1440
```

Use mock mode without a model call:

```env
LLM_PROVIDER=mock
```

## API

- `GET /health`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/current`
- `POST /api/v1/material/upload`
- `GET /api/v1/material/{material_id}/status`
- `POST /api/v1/material/{material_id}/retry`
- `GET /api/v1/material/tree?subject=计算机`
- `GET/POST/PATCH/DELETE /api/v1/kp/...`
- `GET /api/v1/feynman/greeting?kp_id=kp-demo`
- `POST /api/v1/feynman/chat`
- `POST /api/v1/feynman/chat/stream`（知识点讲解流式正文，最终 `done` 事件仍包含完整报告数据）
- `POST /api/v1/feynman/reset`
- `GET /api/v1/feynman/session/{session_id}`
- `GET /api/v1/feynman/sessions`
- `GET /api/v1/feynman/sessions/{session_id}`
- `GET /api/v1/reports?page=1&page_size=20`
- `GET /api/v1/reports/{report_id}`
- `POST /api/v1/reviews/start` (login required)
- `GET /api/v1/reviews/{review_id}` (login required)
- `GET /api/v1/reviews/stats` (login required)
- `GET /api/v1/gaps/review-due` (login required)
- `GET /api/v1/conversations/models` (free-chat model catalog)
- `POST /api/v1/conversations` (login required)
- `GET /api/v1/conversations` (login required)
- `GET /api/v1/conversations/{conversation_id}` (login required)
- `POST /api/v1/conversations/{conversation_id}/messages/stream` (NDJSON incremental reply; login required)
- `POST /api/v1/conversations/{conversation_id}/assessment` (free beginner-mode feedback; login required)

Request:

```json
{
  "session_id": "uuid-string",
  "kp_id": "kp-demo",
  "user_input": "用户对 Dijkstra 算法的讲解"
}
```

`kp-demo` and `kp-demo2` are temporary mock knowledge points. Omitting `kp_id` falls back to `kp-demo` for week-3 compatibility. A session cannot switch knowledge points after the conversation starts; call `/reset` first.

Missing `Authorization` means guest mode. A valid login token can be sent as
`Authorization: Bearer <token>`. Invalid and expired tokens return HTTP 401.
Persisted sessions are bound to the resolved user and cannot be read by another
user.

The runtime graph is:

```text
START -> load_context -> route_input
route_input -> kp_missing | off_topic | ineffective
route_input -> retrieve -> evaluate | report
all branches -> persist_session -> END
```

`retrieve` merges the knowledge point's fixed-page chunks with up to three
single-material Chroma RAG chunks. The BGE embedding model is loaded lazily on
the first real vector operation, so normal API startup does not load the model.

For logged-in users, a `generate_report` response is also persisted to the
`diagnostic_report` table. Dimensions scoring 6 or below are synchronized to
the `knowledge_gap` table when that table is available. Repeating a completed
session is idempotent and does not create duplicate reports or open gaps.
Review sessions are linked to a durable `review_attempt`. Starting or resuming a
review does not increment its gaps' `review_count`; a successfully saved final
report increments each target gap once and atomically updates the report,
attempt, and gaps. Initial low-score gaps are scheduled for the next day.
Guest conversations still return the report to the frontend but are not
persisted.

See `docs/backend-api.md` for frontend integration details.

## Test

```bash
cd /Users/chen/Code/Feynman-Companion-AI-Agent
source .venv/bin/activate
python -m pytest -q backend/tests
```

Run the real week-4 smoke after configuring DeepSeek. It creates a small local
PDF record in `feynman.db` and `uploads/`, then verifies extraction, rubric
generation, dynamic greeting, and the first LangGraph turn:

```bash
python -m backend.scripts.week4_e2e_smoke
```
