# NexusMind

A personal AI knowledge management system. Upload PDFs, articles, audio, or
YouTube transcripts; get citation-grounded answers, automatic claim extraction
with contradiction detection, source-credibility scoring, flashcards, and an
end-to-end studio that turns documents into narrated reels, memes, and
repurposed content.

Built for one user, on one machine. No Docker, no Kubernetes, no cloud bill —
runs natively on Windows (or macOS/Linux with trivial path tweaks).

---

## What you get

- **Library** — upload PDF / TXT / MD / HTML / audio; auto-parse, chunk,
  embed, NER, relation extraction, intelligence summary
- **Q&A** — Groq-hosted Llama 3.3 70B over a hybrid (BM25 + vector + reranker)
  retriever, with inline citations
- **Conversations** — multi-turn Q&A history
- **Annotations** — highlight, note, flashcard, and re-ask any span in any
  document
- **Claims & Contradictions** — automatic claim extraction with cross-document
  contradiction detection via NLI
- **Credibility** — 4-signal composite source score with cohort recompute
- **Flashcards** — SRS deck auto-built from your documents
- **Research briefs** — multi-source synthesis with PDF export
- **Studio** — reel renderer (FFmpeg), narration (Piper/SAPI TTS), meme
  generator (Pillow), repurposed content (scripts, captions, threads),
  brand kits, public share links, per-user quotas

---

## Stack

| Layer | Choice |
|---|---|
| Backend | FastAPI 0.115 + SQLAlchemy 2 (async + sync) + Celery 5 |
| DB | PostgreSQL 16 with `pgvector` (HNSW indexes) |
| Broker / cache | Redis-compatible (Memurai on Windows) |
| Storage | Local filesystem under `./data/files` |
| Frontend | Next.js 14 (App Router) + NextAuth 5 + TanStack Query + Tailwind + shadcn/ui |
| Q&A LLM | Groq `llama-3.3-70b-versatile` (OpenAI-compatible) |
| NER/relations/intelligence/claims LLM | Ollama `qwen2.5:7b-instruct` (local, JSON mode) |
| Chunk embeddings | Google Gemini `gemini-embedding-001` (768-dim) |
| Entity embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local) |
| Claim embeddings | `BAAI/bge-base-en-v1.5` (768-dim, local) |
| NLI | `cross-encoder/nli-deberta-v3-base` (local) |
| NER | spaCy `en_core_web_trf` + GLiNER `urchade/gliner_medium-v2.1` |
| TTS | Piper (preferred) or Windows SAPI via pyttsx3 |
| Video | FFmpeg via `imageio-ffmpeg` |

---

## Prerequisites

Install these once on your machine. All free.

### 1. Python 3.11+
<https://www.python.org/downloads/windows/> — tick **Add python.exe to PATH**.
Verify: `python --version`.

### 2. Node.js 20+ (LTS)
<https://nodejs.org/en/download>. Verify: `node --version`.

### 3. PostgreSQL 16
<https://www.postgresql.org/download/windows/> (EDB installer).
- Use port `5432` (the default).
- Set a password for the `postgres` user. The example config uses `password` —
  if you pick something else, update `DATABASE_URL` and `DATABASE_SYNC_URL`.
- After install, open `psql` and create the database:
  ```sql
  CREATE DATABASE nexusmind;
  ```

### 4. pgvector (Postgres extension)
Two paths:

**A — Stack Builder** (easiest if it's listed): open Application Stack Builder
on your Postgres install and pick pgvector.

**B — Build from source:**
1. Install **Visual Studio Build Tools** with the *Desktop development with
   C++* workload: <https://visualstudio.microsoft.com/visual-cpp-build-tools/>.
2. Open *x64 Native Tools Command Prompt for VS* from the Start Menu.
3. Build and install:
   ```
   set "PGROOT=C:\Program Files\PostgreSQL\16"
   git clone --branch v0.7.4 https://github.com/pgvector/pgvector.git
   cd pgvector
   nmake /F Makefile.win
   nmake /F Makefile.win install
   ```

If both options are painful, use a hosted Postgres with pgvector preinstalled
(Neon, Supabase, Render free tiers) and point `DATABASE_URL` /
`DATABASE_SYNC_URL` at it. The first migration runs `CREATE EXTENSION vector`
for you.

### 5. Redis (Memurai on Windows)
<https://www.memurai.com/get-memurai> — installs as a Windows service on
`localhost:6379`. Verify: `memurai-cli ping` → `PONG`.

(Alternatives: Upstash hosted Redis, or Redis in WSL2.)

### 6. Ollama (for local NER / relations / intelligence / claims LLM)
<https://ollama.com/download>. After install, pull the model the pipeline uses:
```powershell
ollama pull qwen2.5:7b-instruct
ollama pull llama3.1:8b   # fallback model
```
Ollama runs as a background service on `localhost:11434`. If you skip this,
Phase 2 pipelines (NER, relations, intelligence, claims) won't run, but Q&A
still works via Groq.

### 7. FFmpeg (Studio / reel renderer)
The Python package `imageio-ffmpeg` bundles an FFmpeg binary, so for most
users this works out of the box. If you'd rather install system-wide:
<https://www.gyan.dev/ffmpeg/builds/> → add `ffmpeg.exe` to `PATH`.

Only needed for the Studio reel/narration features. Skip if you only want
ingest + Q&A.

---

## API keys

You'll need two API keys for the default configuration: **Groq** (for Q&A) and
**Gemini** (for embeddings). Both have generous free tiers.

| Key | Where to get it | Purpose | Required? |
|---|---|---|---|
| `GROQ_API_KEY` | <https://console.groq.com/keys> | Q&A LLM (`llama-3.3-70b-versatile`) | Yes |
| `GEMINI_API_KEY` | <https://aistudio.google.com/apikey> | Chunk embeddings (`gemini-embedding-001`) | Yes |
| `JWT_SECRET` | Generate locally (32 random bytes) | Backend session signing | Yes |
| `NEXTAUTH_SECRET` | Generate locally (32 random bytes) | NextAuth session signing | Yes |
| `SENTRY_DSN_BACKEND` | <https://sentry.io> project settings | Error tracking (optional) | No |
| `SENTRY_DSN_FRONTEND` | <https://sentry.io> project settings | Error tracking (optional) | No |
| `METRICS_TOKEN` | Generate locally | Bearer token for `/metrics` (optional) | No |

### Where the keys go

All keys live in a single `.env` file at the repo root. Copy the template:

```powershell
Copy-Item .env.example .env
notepad .env
```

Then edit the values. The relevant block looks like this:

```ini
# AI: LLM (Groq, OpenAI-compatible)
GROQ_API_KEY=gsk-...your-key-here...
GROQ_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile

# AI: Embeddings (Google Gemini)
GEMINI_API_KEY=...your-key-here...
EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIM=768

# Auth
JWT_SECRET=...32-random-bytes...
NEXTAUTH_SECRET=...32-random-bytes...
```

### Generating the secrets

Run this in PowerShell to mint a 32-byte base64 secret you can paste in:

```powershell
[System.Convert]::ToBase64String((1..32 | ForEach-Object {Get-Random -Min 0 -Max 256}))
```

Run it twice — once for `JWT_SECRET`, once for `NEXTAUTH_SECRET`.

### Security notes

- `.env` is in `.gitignore` (along with `.env.local`, `*.pem`, `*.key`,
  `secrets/`). It will never be committed.
- The only env file that *is* tracked is `.env.example` — a template with
  placeholder values.
- Rotate `GROQ_API_KEY` / `GEMINI_API_KEY` from the provider dashboards if
  they leak.

---

## First-time setup

From the repo root, in PowerShell:

```powershell
# 1. .env (see "API keys" above)
Copy-Item .env.example .env
notepad .env

# 2. One-shot setup: Python venv, backend + frontend deps, ./data/files,
#    Alembic migrations
.\scripts\setup.ps1
```

If PowerShell blocks the script:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

What `setup.ps1` does:
- Creates `backend/.venv` and installs `backend/requirements.txt`
- Runs `npm install` in `frontend/`
- Creates `./data/files`
- Runs `alembic upgrade head` (creates extension, schema, HNSW indexes)

---

## Running the app

You need **three** terminals (one per process). All commands from the repo
root:

```powershell
# Terminal 1 — FastAPI on :8000
.\scripts\start-api.ps1

# Terminal 2 — Celery worker (parse → chunk → embed → NER → claims → ...)
.\scripts\start-worker.ps1

# Terminal 3 — Next.js on :3000
.\scripts\start-frontend.ps1
```

Then:
- Open <http://localhost:3000>, register, sign in
- Upload a PDF on the Library page
- Watch the pipeline progress (parse → chunk → embed → NER → relations →
  intelligence → claims → contradictions → credibility)
- Ask a question on the Q&A page

Spot-check endpoints:
- <http://localhost:8000/health> → `{"status":"ok"}`
- <http://localhost:8000/readiness> → `{"status":"ready"}` when Postgres,
  Redis, and the storage dir are all reachable
- <http://localhost:8000/docs> → OpenAPI

### Worker queue note (Windows)

Celery on Windows must use `--pool=solo`. The start script handles this; if
you ever invoke `celery` by hand, include `--pool=solo`.

---

## Tests

```powershell
cd backend
.\.venv\Scripts\activate
pytest
```

The Postgres-touching tests auto-skip if the DB isn't reachable. To run them
in isolation, stop the API first or point `DATABASE_URL` at a separate test
DB.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `psycopg2.OperationalError: could not connect to server` | Postgres service isn't running. Open `services.msc`, find `postgresql-x64-16`, start it. Or check the password in `.env`. |
| `ERROR: extension "vector" is not available` during migration | pgvector isn't installed. Redo prerequisite 4. |
| Celery hangs or `ValueError: not enough values to unpack` | Worker pool needs `--pool=solo` on Windows. Use the start script. |
| `OPENAI_API_KEY required` | Old env var. You want `GROQ_API_KEY` + `GEMINI_API_KEY`. |
| `connection refused` to `localhost:11434` | Ollama isn't running. Start the Ollama desktop app or `ollama serve`. Q&A still works without it; Phase 2 pipelines won't. |
| Frontend 401 loops | `NEXTAUTH_SECRET` mismatch between server restarts, or `NEXTAUTH_URL` doesn't match the URL you're loading. |
| Reel render fails with `ffmpeg not found` | Either reinstall `imageio-ffmpeg`, or install FFmpeg and add it to `PATH`. |
| `429` from Groq during heavy use | Free-tier rate limit. Wait, or upgrade the Groq plan. |

---

## Where things live

- **Uploaded files & generated media:**
  `./data/files/{user_id}/{document_id}/...` — also holds per-document
  `parsed.json`, reel renders, narrations, generated memes
- **Postgres data:** wherever the Postgres installer put it (default
  `C:\Program Files\PostgreSQL\16\data`)
- **Frontend build cache:** `frontend/.next`
- **Logs:** `./logs/` (gitignored)

The entire `data/` tree is gitignored at any depth — uploads, generated
videos/audio, and ML model weights never leave your machine.

---

## Layout

```
NexusMind/
├── .env.example           Env template (only env file in git)
├── README.md              You are here
├── scripts/               PowerShell setup + start scripts
├── backend/
│   ├── alembic/           DB migrations (pgvector + HNSW)
│   ├── app/
│   │   ├── api/           FastAPI routes
│   │   ├── auth/          JWT, bcrypt, get_current_user dependency
│   │   ├── core/          config, structlog, exceptions
│   │   ├── db/            async + sync SQLAlchemy sessions
│   │   ├── models/        ORM models
│   │   ├── schemas/       Pydantic v2 schemas
│   │   ├── services/      storage, embedding, llm, retrieval, chunking,
│   │   │                  claims, credibility, contradictions, media, ...
│   │   ├── workers/       Celery tasks
│   │   └── main.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app/               App-Router routes ((auth) + (app) groups)
│   ├── components/        Feature components + shadcn/ui primitives
│   ├── hooks/, services/, lib/, types/
│   └── package.json
└── data/files/            Uploads + generated media (created at first run)
```

---

## License

Personal project — no license declared. All rights reserved.
