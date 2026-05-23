# NexusMind — Phase 1 MVP (native Windows setup)

A personal AI knowledge management platform. Upload PDFs / TXT / MD, get
citation-grounded answers from your own documents.

## Stack

- **Backend:** FastAPI 0.115 + SQLAlchemy 2 (async) + Celery 5
- **DB:** PostgreSQL 16 with `pgvector` (HNSW index)
- **Cache / broker:** Redis-compatible (Memurai or Redis)
- **Storage:** local filesystem (`./data/files`)
- **AI:** Google Gemini `gemini-embedding-001` (768-dim) for embeddings + Groq
  `llama-3.3-70b-versatile` for the LLM (OpenAI-compatible API)
- **Frontend:** Next.js 14 (App Router) + NextAuth 5 + TanStack Query + Tailwind

## Prerequisites

You'll install five things on your machine. All free, all native Windows
binaries — no Docker, no WSL required.

### 1. Python 3.11+
<https://www.python.org/downloads/windows/>
During install, tick **"Add python.exe to PATH"**. Verify: `python --version`.

### 2. Node.js 20+
<https://nodejs.org/en/download> (LTS).
Verify: `node --version`, `npm --version`.

### 3. PostgreSQL 16
<https://www.postgresql.org/download/windows/> → EDB installer.
- Pick port `5432` (default).
- Set the `postgres` user password to something you'll remember (the example
  config uses `password` — change it everywhere if you pick differently).
- After install, open **Stack Builder** (it autostarts) or **pgAdmin**, and
  create a database named `nexusmind`. From a Postgres shell (`psql`):
  ```sql
  CREATE DATABASE nexusmind;
  ```

### 4. pgvector
The Postgres extension. Two paths, easiest first:

**Option A — Stack Builder (if it's listed):** open Application Stack Builder
on your Postgres install and install pgvector if shown.

**Option B — Manual install (most common):**
1. Install **Visual Studio Build Tools** with the "Desktop development with
   C++" workload: <https://visualstudio.microsoft.com/visual-cpp-build-tools/>.
2. Open the **x64 Native Tools Command Prompt for VS** (from Start Menu).
3. Build and install pgvector:
   ```
   set "PGROOT=C:\Program Files\PostgreSQL\16"
   git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git
   cd pgvector
   nmake /F Makefile.win
   nmake /F Makefile.win install
   ```
4. The extension is now available. The first DB migration runs
   `CREATE EXTENSION vector` for you.

If that's too painful, you can use a free hosted Postgres with pgvector
preinstalled (Neon, Supabase, Render — all have free tiers) and just point
`DATABASE_URL` / `DATABASE_SYNC_URL` at it. The code doesn't care where Postgres
lives.

### 5. Redis (Memurai for Windows)
Native Redis isn't supported on Windows. Use **Memurai Developer** (free, fully
Redis-compatible): <https://www.memurai.com/get-memurai>.

After install it runs as a Windows service on `localhost:6379` automatically.
Verify: `memurai-cli ping` → `PONG`.

(Alternatives: Upstash free hosted Redis, or run Redis inside WSL2.)

## First-time setup

From `C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind`, in PowerShell:

```powershell
# 1. Create your .env from the template
Copy-Item .env.example .env

# 2. Edit .env and set:
#    GROQ_API_KEY        -> https://console.groq.com/keys
#    GEMINI_API_KEY      -> https://aistudio.google.com/apikey
#    JWT_SECRET          -> any 32-byte random string
#    NEXTAUTH_SECRET     -> any 32-byte random string
#    DATABASE_URL/_SYNC  -> adjust password if not "password"
notepad .env

# 3. Generate two secrets if you want
[System.Convert]::ToBase64String((1..32 | ForEach-Object {Get-Random -Min 0 -Max 256}))

# 4. Run the setup script
#    (creates Python venv, installs backend + frontend deps,
#     creates ./data/files, runs Alembic migrations)
.\scripts\setup.ps1
```

If PowerShell blocks the script, allow it for this session:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run it

You need **three** terminals open at the same time (one per process). From the
project root in each:

```powershell
# Terminal 1 — FastAPI
.\scripts\start-api.ps1

# Terminal 2 — Celery worker (parses, chunks, embeds)
.\scripts\start-worker.ps1

# Terminal 3 — Next.js frontend
.\scripts\start-frontend.ps1
```

Then open <http://localhost:3000>, register, upload a PDF, and try the Q&A flow.

Spot-check endpoints:
- <http://localhost:8000/health> → `{"status":"ok"}`
- <http://localhost:8000/readiness> → `{"status":"ready"}` when Postgres,
  Redis, and the storage dir are all available.

## Tests

```powershell
cd backend
.\.venv\Scripts\activate
pytest tests/test_jwt.py tests/test_chunking.py tests/test_embedding.py tests/test_llm.py
```

The integration tests (`test_auth.py`, `test_ingest.py`, `test_qa.py`) need
Postgres reachable; they auto-skip otherwise. To run them,
make sure the API is *not* running (so the test DB connection isn't competing)
or point `DATABASE_URL` at a separate test DB.

## Troubleshooting

- **`psycopg2.OperationalError: could not connect to server`** — Postgres
  service isn't running. Open *Services* (`services.msc`), find
  `postgresql-x64-16`, start it. Or check the password matches your `.env`.
- **`ERROR: extension "vector" is not available`** when running migrations —
  pgvector isn't installed. Re-do step 4 of prerequisites.
- **Celery hangs / "ValueError: not enough values to unpack" on Windows** — the
  worker pool needs to be `solo`. The start script sets `--pool=solo`; if you
  run celery manually, include that flag.
- **`OPENAI_API_KEY required`** — that env var no longer exists; you want
  `GROQ_API_KEY` and `GEMINI_API_KEY` in `.env`.

## Where files live

- Uploaded files: `./data/files/{user_id}/{document_id}/{filename}` plus a
  `parsed.json` per document.
- Postgres data: wherever the Postgres installer put it (default
  `C:\Program Files\PostgreSQL\16\data`).
- Frontend build cache: `frontend/.next`.

## Layout

```
NexusMind/
├── .env.example           Environment template
├── README.md              This file
├── scripts/               PowerShell setup + start scripts
├── backend/
│   ├── alembic/           DB migrations (pgvector + HNSW)
│   ├── app/
│   │   ├── api/           FastAPI routes (auth, documents, qa, health)
│   │   ├── auth/          JWT, bcrypt, get_current_user dep
│   │   ├── core/          config, structlog, exceptions
│   │   ├── db/            async + sync SQLAlchemy sessions
│   │   ├── models/        ORM models
│   │   ├── schemas/       Pydantic v2
│   │   ├── services/      storage, embedding, llm, retrieval, chunking
│   │   ├── workers/       Celery tasks: parse → chunk → embed
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app/               App-Router routes (auth + app group)
│   ├── components/        UI primitives + feature components
│   ├── hooks/, services/, lib/, types/
│   └── package.json
└── data/files/            Uploaded files (created at first run)
```

The old Docker files (`docker-compose.yml`, `backend/Dockerfile`,
`frontend/Dockerfile`) are no longer used. Safe to delete.
