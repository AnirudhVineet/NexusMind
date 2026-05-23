# NexusMind Phase 2 — Run Guide

Project root: `C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind`. All paths below are relative to that unless absolute.

---

## 0. What's already done vs what you still need to do

This reflects the current state of your machine.

| ✓ Done | ✗ Still to do |
|---|---|
| Postgres (Neon cloud, configured in `.env`) | **Apply Phase 2 migrations** — `alembic upgrade head` |
| Redis running locally | **Pull the Ollama model** — `ollama pull qwen2.5:7b-instruct` |
| Ollama installed | **Rotate API keys** (urgent — see §1) |
| Backend `.venv` set up with Phase 1 deps | **Install Phase 2 Python deps** — `pip install -r requirements.txt` (re-run to pick up new lines) |
| Frontend `npm install` done | **Install new D3 deps** — `npm install` (re-run to pick up new lines) |
| `.env` has Phase 1 + Phase 2 vars | |
| `JWT_SECRET` + `NEXTAUTH_SECRET` generated | |

Sections §1–§4 are the four pending items, in order. Section §5 onwards is daily run + reference.

---

## 1. ⚠ Rotate exposed API keys (urgent)

Your current `GROQ_API_KEY`, `GEMINI_API_KEY`, `JWT_SECRET`, and `NEXTAUTH_SECRET` were shared in a chat transcript. Rotate them before going further.

- **Groq**: <https://console.groq.com/keys> → delete the existing key → **Create API Key** → paste new value into `GROQ_API_KEY=` in `.env`.
- **Gemini**: <https://aistudio.google.com/app/apikey> → delete and recreate → paste into `GEMINI_API_KEY=`.
- **JWT_SECRET / NEXTAUTH_SECRET**: regenerate each, separately:
  ```powershell
  python -c "import secrets; print(secrets.token_urlsafe(48))"
  ```
  Run twice; paste one value into `JWT_SECRET=`, the *other* into `NEXTAUTH_SECRET=`.

If you regenerate `NEXTAUTH_SECRET`, all existing browser sessions become invalid — sign out and back in.

---

## 2. Install Phase 2 Python + npm deps

Phase 2 added: `spacy`, `en_core_web_trf` wheel, `gliner`, `sentence-transformers`, `rapidfuzz`, `bertopic`, `textstat` to `backend/requirements.txt`, and `d3-*` packages to `frontend/package.json`.

```powershell
# Backend (~3–5 minutes; downloads several wheels)
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind\backend
.\.venv\Scripts\pip.exe install -r requirements.txt

# Frontend (fast)
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind\frontend
npm install
```

Note: heavy ML *models* (spaCy transformer, GLiNER, MiniLM) do **not** download here — they download on first Celery task execution (see §6).

---

## 3. Apply Phase 2 migrations

You need migrations `0002_kg_tables`, `0003_document_intelligence`, `0004_task_runs` applied to your Neon database. Alembic walks forward from your current revision:

```powershell
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind\backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\alembic.exe current
```

The `current` line at the end should print something containing `0004`. If it doesn't, scroll up — alembic emits clear errors.

**Neon-specific note:** the migration runs `CREATE EXTENSION IF NOT EXISTS vector;` which Neon supports. If you ever see `permission denied to create extension`, your Neon project needs pgvector enabled in its dashboard.

---

## 4. Pull the Ollama model

```powershell
ollama pull qwen2.5:7b-instruct
```

About 4.7 GB. Verify when done:

```powershell
ollama list
curl http://localhost:11434/api/tags
```

The first should show `qwen2.5:7b-instruct` with a size and digest. The second is a JSON listing of installed models.

(Optional) Replace the placeholder in `backend/models.lock` with the real digest from `ollama list`. Not required for it to work — the digest pin is for reproducibility.

---

## 5. Daily run — three terminals

After §1–§4 are done, this is all you ever need.

### Terminal 1 — FastAPI backend

```powershell
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind
.\scripts\start-api.ps1
```

API at <http://localhost:8000>, OpenAPI docs at <http://localhost:8000/docs>, Prometheus metrics at <http://localhost:8000/metrics>.

### Terminal 2 — Celery worker

```powershell
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind
.\scripts\start-worker.ps1
```

This subscribes to all five queues (`default,ner,relations,intelligence,maintenance`). Without this running, Phase 2 tasks queue up but never execute.

### Terminal 3 — Frontend

```powershell
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind
.\scripts\start-frontend.ps1
```

UI at <http://localhost:3000>. Sign in, upload a document, then watch Terminal 2 process it.

### Optional terminal 4 — Celery beat

Only needed for the weekly edge-prune and daily topic recompute. Skip for development:

```powershell
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind\backend
Get-Content ..\.env | ForEach-Object { if ($_ -match "^\s*([^#=]+)=(.*)$") { Set-Item -Path "Env:$($matches[1].Trim())" -Value $matches[2].Trim() } }
.\.venv\Scripts\celery.exe -A app.workers.celery_app beat --loglevel=info
```

---

## 6. What to expect on the very first upload

The first time the worker runs a Phase 2 task, it spends ~2 minutes downloading models to `%USERPROFILE%\.cache\huggingface\hub`:

| Model | Size | Triggered by |
|---|---|---|
| `urchade/gliner_medium-v2.1` | ~830 MB | First `extract_entities` task |
| `sentence-transformers/all-MiniLM-L6-v2` | ~90 MB | First `extract_entities` task |
| spaCy `en_core_web_trf` | ~440 MB | Installed via pip wheel — no extra download |

Watch Terminal 2 for download progress. Subsequent runs are instant.

After upload, you should see this sequence in the worker log:

```
parse_document → chunk_document → embed_chunks
  → extract_entities.done (counts entities)
  → extract_relations.done (edges_written=N)
  → compute_intelligence.done (tag_count=M, insight_count=K)
```

Then refresh in the browser:
- `/library` — your doc appears with `processing_status=complete` once `embed_chunks` finishes (Phase 2 enrichment continues in background).
- `/library/<doc-id>` — Document Intelligence pane populates once `compute_intelligence.done` lands.
- `/graph` — Knowledge Graph populates once `extract_relations.done` lands.

---

## 7. Health checks

Run any of these at any time to verify components:

```powershell
# Neon Postgres
.\.venv\Scripts\python.exe -c "from sqlalchemy import create_engine, text; import os; from dotenv import load_dotenv; load_dotenv('../.env'); print(create_engine(os.environ['DATABASE_SYNC_URL']).connect().execute(text('select 1')).scalar())"

# Redis
redis-cli ping        # or: docker exec -it nexusmind-redis redis-cli ping

# Ollama
curl http://localhost:11434/api/tags

# Backend
curl http://localhost:8000/health
curl http://localhost:8000/metrics    # Prometheus output

# Celery: registered tasks (should list extract_entities, extract_relations, compute_intelligence, etc.)
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind\backend
.\.venv\Scripts\celery.exe -A app.workers.celery_app inspect registered

# Celery queue depths
redis-cli LLEN ner
redis-cli LLEN relations
redis-cli LLEN intelligence
```

---

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `pydantic_core ValidationError` on backend boot | `.env` missing a required value | Re-check `.env` — it must be at project root, not in `backend/`. The `start-api.ps1` script loads it from there. |
| `ModuleNotFoundError: No module named 'spacy'` / `'gliner'` / `'sentence_transformers'` | §2 not done | Re-run `pip install -r requirements.txt` |
| `relation "entities" does not exist` | §3 not done | `alembic upgrade head` |
| `permission denied to create extension` (Postgres) | Neon pgvector not enabled | Enable pgvector in Neon dashboard for your project |
| `httpx.ConnectError` calling Ollama | Ollama service stopped, or model not pulled | `curl http://localhost:11434/api/tags`; `ollama pull qwen2.5:7b-instruct` |
| Worker idle, NER tasks not picked up | Worker started without `-Q` queue list | Make sure `start-worker.ps1` includes `-Q default,ner,relations,intelligence,maintenance`. If running celery by hand, add the same flag. |
| Worker hangs ~2 min on first task | First-time HuggingFace model downloads | Expected — see §6. Wait it out. |
| `Pool implementation 'prefork' not supported on this platform` | Missing `--pool=solo` on Windows | Already set in `start-worker.ps1`. If running celery by hand, add `--pool=solo`. |
| Graph page empty after upload | NER/relations are background; document is "complete" before graph is populated | Watch worker log for `extract_relations.done`. Refresh `/graph` afterward. |
| Intelligence pane stuck on "Pending" | `compute_intelligence` task hasn't finished, or Ollama errored | Check Terminal 2 log for errors. Click "Recompute" to retry. |
| Frontend 401s | Stale session cookie | Sign out, clear `localhost:3000` cookies, sign in again. |
| `Sentry not initialized` warning | `SENTRY_DSN_BACKEND` blank | Ignore — Sentry is optional. |

---

## 9. Stop everything

`Ctrl+C` in each terminal. Redis and Ollama keep running as background services — that's fine, they're idle. Neon is a managed service so no action needed.

To wipe just the Phase 2 tables (keeping Phase 1 data + users):

```powershell
cd C:\Users\aniru\OneDrive\Desktop\Projects\NexusMind\backend
.\.venv\Scripts\alembic.exe downgrade 0001    # drops 0002+0003+0004
.\.venv\Scripts\alembic.exe upgrade head      # recreates them
```

To start completely fresh (wipes everything):

```powershell
.\.venv\Scripts\alembic.exe downgrade base
.\.venv\Scripts\alembic.exe upgrade head
```

---

## 10. Full preflight reference (for first-time setup on a new machine)

Skip this section unless you're standing up the project from scratch elsewhere.

1. Clone the repo, `cd` to project root.
2. `Copy-Item .env.example .env` and fill in the required vars (Groq, Gemini, JWT, NextAuth, DB URL).
3. Generate secrets with `python -c "import secrets; print(secrets.token_urlsafe(48))"` (twice — once for JWT, once for NextAuth).
4. Make sure Postgres (with pgvector) and Redis are reachable on the URLs in `.env`.
5. Install Ollama (<https://ollama.com/download/windows>) and `ollama pull qwen2.5:7b-instruct`.
6. Run `.\scripts\setup.ps1` — creates `.venv`, installs deps, runs migrations, installs frontend deps.
7. Proceed to §5.
