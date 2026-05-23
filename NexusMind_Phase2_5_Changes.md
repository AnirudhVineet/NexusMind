# NexusMind — Cumulative Changes Reference
## What Was Built vs. Original Specs (Phases 1 → 2 → 2.5 → 3)

This document is a full accounting of every deviation, addition, and substitution
made relative to the original Phase 1, 2, and 3 prompts. Use it to write a
Phase 4 prompt that builds on actual implemented state rather than original specs.

Last updated: Phase 3 complete (2026-05-19).

---

## 1. Infrastructure Overhaul (Phase 1 → Actual)

### Original Phase 1 Spec
- Docker Compose stack: `postgres`, `redis`, `minio`, `api`, `worker`, `frontend`
- Object storage: **MinIO** (S3-compatible), `boto3` client, `S3_ENDPOINT_URL` env var
- Embedding model: OpenAI `text-embedding-3-small` (1536-dim, paid API)
- LLM: OpenAI `gpt-4o-mini` (paid API)
- Error tracking: Sentry (frontend + backend)
- Container networking between services

### What Was Actually Built
- **No Docker** — native Windows binaries only (no WSL required)
- **No MinIO** — replaced with local filesystem (`StorageService` wraps `pathlib`,
  files stored at `./data/files/{user_id}/{document_id}/{filename}`)
- **No S3 env vars** — `S3_*` vars are absent; storage path is configured by
  `STORAGE_DIR` in `backend/app/core/config.py`
- **No Sentry** — observability is structlog JSON to stdout + Prometheus metrics
  (`/metrics` endpoint via `backend/app/api/metrics.py`)
- PostgreSQL 16 + pgvector and Memurai (Windows Redis) run as native services
- PowerShell scripts replace `docker compose up`:
  `scripts/start-api.ps1`, `scripts/start-worker.ps1`, `scripts/start-frontend.ps1`

### Implication for Phase 4
Phase 4 must not reintroduce Docker or S3 references. Storage is local filesystem.
Any cloud migration should be treated as a separate parallel deliverable, not a
prerequisite. A `NexusMind_Supabase_Migration_Plan.md` already exists in `Prompt/`
if a hosted-DB path is wanted.

---

## 2. AI Stack — Actual State (Phase 3 complete)

| Component | Original Spec | Actual Implementation |
|---|---|---|
| Chunk embeddings | OpenAI `text-embedding-3-small` (1536-dim) | Google Gemini `text-embedding-004` (768-dim, free tier) |
| LLM (Q&A) | OpenAI `gpt-4o-mini` | Groq `llama-3.3-70b-versatile` (OpenAI-compatible, free tier) |
| LLM (local — NER/relations/intelligence/claims/cards) | Ollama `qwen2.5:7b-instruct` | Ollama `qwen2.5:7b-instruct` ✓ |
| NER | spaCy `en_core_web_trf` + GLiNER | spaCy `en_core_web_trf` + GLiNER `urchade/gliner_medium-v2.1` ✓ |
| Entity embeddings | `all-MiniLM-L6-v2` (384-dim) | `all-MiniLM-L6-v2` (384-dim) ✓ |
| Claim embeddings | `bge-base-en-v1.5` (768-dim) | `BAAI/bge-base-en-v1.5` (768-dim) ✓ |
| Reranker | `BAAI/bge-reranker-base` | ✓ `BAAI/bge-reranker-base` via `CrossEncoder` — implemented Phase 3.1 |
| BM25 | PostgreSQL `tsvector`/GIN | ✓ `tsvector` + GIN index + trigger — implemented Phase 3.1 |
| NLI (contradictions) | `cross-encoder/nli-deberta-v3-base` | `cross-encoder/nli-deberta-v3-base` ✓ |
| Audio transcription | OpenAI Whisper API (paid) | Groq Whisper API (`whisper-large-v3-turbo`, free tier) |
| OCR | AWS Textract (paid) | Gemini Vision fallback for scanned PDFs |
| Web extraction | Playwright | BeautifulSoup + httpx (`services/web_scraper.py`) |

**Critical vector dimension**: chunks store 768-dim vectors (Gemini). The HNSW index
in `0001_initial_schema.py` uses `vector(768)`. All retrieval code must use 768-dim.

---

## 3. API Route Structure — Actual State (Phase 3 complete)

### Route Prefix Pattern
Phase 1 routes were implemented **without** an `/api` prefix:
- `POST /auth/register`, `POST /auth/token`, `GET /auth/me`
- `POST /ingest`, `GET /documents`, `GET /documents/{id}`, `DELETE /documents/{id}`
- `POST /qa`, `POST /qa/stream`
- `GET /health`, `GET /readiness`, `GET /metrics`

Phase 2+ routes use an `/api` prefix:
- `GET /api/graph`, `POST /api/graph/expand`
- `GET /api/conflicts`, `GET /api/conflicts/{id}`
- `GET /api/claims`
- `GET /api/documents/{id}/credibility`
- `PUT /api/credibility/weights`
- `GET /api/intelligence/{document_id}`
- `POST /api/search`
- `GET /api/conversations`, `GET /api/conversations/{id}`, `PATCH /api/conversations/{id}`, `DELETE /api/conversations/{id}`
- `POST /api/ingest/url`, `POST /api/ingest/url-content`, `POST /api/ingest/youtube`, `POST /api/ingest/audio`, `POST /api/ingest/notion`, `POST /api/ingest/zip`
- `POST /api/annotations`, `GET /api/annotations`, `PATCH /api/annotations/{id}`, `DELETE /api/annotations/{id}`, `GET /api/annotations/export`
- `POST /api/notes/highlight`
- `POST /api/cards/generate`, `GET /api/cards/due`, `POST /api/cards/{id}/review`, `PATCH /api/cards/{id}`, `DELETE /api/cards/{id}`, `GET /api/cards/stats`
- `GET /api/extension/token`, `POST /api/extension/token/rotate`

The frontend `apiFetch` utility uses `http://localhost:8000` as base. Phase 4 must
maintain this mixed prefix scheme or migrate everything — don't add new routes
inconsistently.

---

## 4. Database Schema — Actual State (Phase 3 complete)

### Migrations Applied (in order)

| Migration | What It Does |
|---|---|
| `0001_initial_schema` | `users`, `documents`, `chunks`, `conversations`, `messages` |
| `0002_kg_tables` | `entities`, `entity_edges`, `topics`, `document_topic` |
| `0003_document_intelligence` | `document_intelligence` JSONB column on `documents` |
| `0004_task_runs` | `task_runs` (worker idempotency tracking) |
| `0005_claims` | `claims` (extracted atomic claims per chunk) |
| `0006_claim_contradictions` | `claim_contradictions` (NLI-verified contradiction pairs) |
| `0007_credibility` | `source_type_signals` + credibility columns on `documents` |
| `0008_chunk_tsvector` | `tsv tsvector` column + GIN index + auto-update trigger on `chunks` |
| `0009_document_source_url` | `source_url` column on `documents` |
| `0010_document_ingestion_metadata` | `ingestion_metadata` JSONB column on `documents` |
| `0011_document_batch_id` | `ingestion_batch_id` UUID on `documents` (ZIP bundle grouping) |
| `0012_annotations` | `annotations` table (highlight text, char positions, tags, color, embedding) |
| `0013_flashcards` | `flashcards` + `flashcard_reviews` tables (SM-2 spaced repetition) |
| `0014_user_extension_token` | `extension_token_issued_at` on `users` (extension JWT revocation) |

### Key Column Additions to `documents` (Phases 2.5 + 3)
```
credibility_score           FLOAT     composite [0,1] score
recency_signal              FLOAT
source_type_signal          FLOAT
cross_source_agreement      FLOAT
citation_density            FLOAT
credibility_computed_at     TIMESTAMPTZ
document_intelligence       JSONB     summaries, insights, topics, reading metrics
source_url                  TEXT      for web/youtube/notion ingestion
ingestion_metadata          JSONB     per-source metadata (title, captured_at, etc.)
ingestion_batch_id          UUID      groups files from a ZIP import
```

### Knowledge Graph Storage Decision
Phase 2 spec offered two paths (PostgreSQL adjacency vs. Neo4j). The implementation
chose **PostgreSQL adjacency tables** — `entities` + `entity_edges`. Neo4j is NOT
in use. Appropriate for < 50K entities per the spec criterion.

---

## 5. Celery Worker Architecture — Actual State (Phase 3 complete)

### Full Pipeline (Phase 3)
```
parse → chunk → embed → ner → relations → intelligence
                                         → claims → contradictions → credibility → cohort_recompute
```
Post-pipeline (triggered separately): `generate_cards` (user-initiated per document)

### Celery Queues (actual — 9 queues)

| Queue | Tasks | Speed profile |
|---|---|---|
| `default` | parse, chunk, embed | Fast — file I/O + Gemini API, < 5s each |
| `ner` | extract_entities | Medium — spaCy/GLiNER, ~10–20s per doc |
| `relations` | extract_relations | Slow — Ollama JSON call per chunk |
| `intelligence` | compute_intelligence, assign_topics | Slow — Ollama map-reduce |
| `claims` | extract_claims | Slow — Ollama JSON + bge-base embeddings |
| `nli` | detect_contradictions | Medium — DeBERTa cross-encoder |
| `credibility` | compute_credibility, recompute_cohort | Fast — SQL aggregates |
| `ocr` | ocr tasks | Variable — Gemini Vision |
| `transcription` | transcribe_audio, fetch_youtube_transcript | Slow — Groq Whisper |
| `cards` | generate_cards | Slow — Ollama JSON |
| `maintenance` | prune_edges, recompute_topics | Background |

### Multi-Worker Startup (Phase 3 change — replaces single-worker command)
`scripts/start-worker.ps1` now launches **5 separate worker processes** to prevent
slow Ollama tasks from blocking the fast parse/embed path:

```
NM-fast  : default
NM-ner   : ner
NM-llm   : relations,intelligence,claims
NM-nli   : nli,credibility
NM-misc  : ocr,transcription,cards,maintenance
```

**Do not use the old single-worker command** — it serialises all stages and leaves
new documents stuck at `queued` for several minutes while Ollama tasks run.

### Worker Files (all phases)
- `workers/parse.py` — parse_document (PDF/text/audio routing, OCR fallback)
- `workers/chunk.py`
- `workers/embed.py`
- `workers/ner.py` — extract_entities, extract_relations
- `workers/relations.py`
- `workers/intelligence.py` — compute_intelligence, assign_topics
- `workers/claims.py` — extract_claims
- `workers/contradictions.py` — detect_contradictions
- `workers/credibility.py` — compute_credibility, recompute_cohort
- `workers/annotations.py` — project_annotation_task (graph entity creation)
- `workers/cards.py` — generate_cards
- `workers/idempotency.py` — shared idempotency context manager
- `workers/maintenance.py` — prune_low_conf_edges, recompute_topics

---

## 6. Backend Services — Actual State (Phase 3 complete)

| Service File | Responsibility |
|---|---|
| `services/ner.py` | spaCy + GLiNER inference, merging |
| `services/entity_embedding.py` | `all-MiniLM-L6-v2` entity embedding |
| `services/entity_dedup.py` | cosine + fuzzy dedup on entity insert |
| `services/intelligence.py` | Ollama map-reduce summarization, key insights |
| `services/topics.py` | BERTopic corpus clustering, tag assignment |
| `services/graph.py` | Graph queries, neighbor expansion |
| `services/claims.py` | Ollama JSON-mode claim extraction, bge-base embedding |
| `services/contradiction.py` | HNSW candidate stage + DeBERTa NLI verification |
| `services/credibility.py` | 4-signal composite credibility computation |
| `services/llm_local.py` | Ollama-specific async/sync client |
| `services/llm.py` | Groq streaming + non-streaming client |
| `services/ocr.py` | Gemini Vision OCR for scanned PDFs |
| `services/retrieval.py` | Hybrid search: BM25 + vector + RRF + bge-reranker |
| `services/sm2.py` | Pure SM-2 spaced repetition algorithm |
| `services/cards.py` | Ollama flashcard generation from chunks |
| `services/web_scraper.py` | httpx + BeautifulSoup URL scraping |
| `services/youtube_ingest.py` | youtube-transcript-api transcript fetching |
| `services/notion_ingest.py` | notion-client page fetching + Markdown conversion |
| `services/storage.py` | Local filesystem storage abstraction |
| `services/embedding.py` | Gemini text-embedding-004 client |

---

## 7. Frontend — Pages and Components (Phase 3 complete)

### All Pages

| Route | Added In | Description |
|---|---|---|
| `/sign-in`, `/sign-up` | Phase 1 | Auth forms |
| `/upload` | Phase 1 → Phase 3 | File, URL, YouTube, audio, Notion, ZIP upload tabs |
| `/library` | Phase 1 | Document list with credibility badges |
| `/library/[id]` | Phase 2 | Document detail, intelligence pane, annotation overlay, cards panel |
| `/qa` | Phase 1 → Phase 3 | Streaming Q&A with conversation sidebar |
| `/graph` | Phase 2 | D3.js knowledge graph explorer |
| `/conflicts` | Phase 2.5 | Contradiction pairs list + detail |
| `/search` | Phase 3.1 | Hybrid search with filter sidebar |
| `/notes` | Phase 3.5 | Annotations list, filterable by tag/document/date |
| `/flashcards` | Phase 3.6 | SM-2 review session with stats dashboard |
| `/connections` | Phase 3.4 | Browser extension token management + install instructions |

### Key Components (Phase 3 additions)

**Search** (`components/search/`):
- `SearchBar.tsx`, `FilterPanel.tsx`, `ResultCard.tsx`

**Q&A** (`components/qa/`):
- `ConversationSidebar.tsx` — collapsible conversation list with rename/delete
- `StreamingMessage.tsx` — SSE token streaming with citation rendering

**Ingest** (`components/upload/`):
- `IngestUrlForm.tsx` — URL and YouTube ingestion
- `IngestNotionForm.tsx` — Notion page import

**Annotations** (`components/annotations/`):
- `AnnotationPopover.tsx`, `AnnotationCard.tsx`, `DocumentViewer.tsx`

**Flashcards** (`components/cards/`):
- `ReviewModal.tsx` — flip animation, 4-button SM-2 rating, keyboard shortcuts 1–4
- `CardEditor.tsx`, `DueBadge.tsx`, `DocumentCardsPanel.tsx`

### Hooks (Phase 3 additions)
- `useSearch.ts`, `useStreamingQa.ts`, `useConversations.ts`
- `useAnnotations.ts`, `useFlashcards.ts`, `useExtensionToken.ts`

### Service Clients (Phase 3 additions)
- `services/search.ts`, `services/annotations.ts`, `services/flashcards.ts`
- `services/ingest.ts`, `services/notion.ts`, `services/extension.ts`

### Navigation
`components/app-shell.tsx` nav links: Dashboard, Upload, Search, Q&A, Library,
Graph, Conflicts, Notes, Flashcards, Connections.

---

## 8. Browser Extension — Phase 3.4

A full browser extension lives at `extension/` (separate from the Next.js frontend).

| File | Purpose |
|---|---|
| `src/manifest.json` | MV3, declares popup, background SW, content script |
| `src/background.ts` | Service worker: context menu, SAVE_PAGE + SEARCH message handlers |
| `src/content.ts` | Content script: Readability.js page extraction, selection capture |
| `src/popup/App.tsx` | Tabbed popup (Search / Save / Settings) |
| `src/popup/SearchPanel.tsx` | Debounced search against `/api/search` |
| `src/popup/SavePanel.tsx` | "Save this page" via `/api/ingest/url-content` |
| `src/popup/SettingsPanel.tsx` | Extension token input, persisted to `chrome.storage.local` |

**Build:** `cd extension && npm install && npm run build` → load `dist/` unpacked.

**Extension token lifecycle:** issued via `GET /api/extension/token` (30-day JWT with
`scope: "extension"` claim), rotated via `POST /api/extension/token/rotate` which
updates `users.extension_token_issued_at` to invalidate older tokens. The
`/connections` page in the web app is the token management UI.

---

## 9. Auth & Session Model

Base JWT flow unchanged from Phase 1. Phase 3 additions:
- `users.extension_token_issued_at` (migration 0014) for extension token rotation
- `create_extension_token()` in `auth/jwt.py` — 30-day, `scope: "extension"` claim
- `get_extension_user()` dependency in `auth/dependencies.py` — validates scope + iat

The `workspace_id` field mentioned in the Phase 2 spec was **not added** — single-user
per account remains. Collaboration is deferred to Phase 4.

---

## 10. Observability — Actual State (Phase 3 complete)

| Component | Status |
|---|---|
| structlog JSON logs | ✓ |
| Prometheus metrics at `/metrics` | ✓ |
| Grafana OSS dashboards | ✓ — 4 provisioned JSON files at `ops/grafana/dashboards/`: `ingestion.json`, `retrieval.json`, `ai_usage.json`, `system.json` |
| Sentry (backend + frontend) | Not implemented — no paid service required |

---

## 11. Environment Variables — Actual `.env` Keys (Phase 3 complete)

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/nexusmind
DATABASE_SYNC_URL=postgresql://postgres:password@localhost:5432/nexusmind

# Cache / broker
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# AI — Q&A and audio transcription
GROQ_API_KEY=...
GROQ_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
GROQ_WHISPER_MODEL=whisper-large-v3-turbo

# AI — Embeddings
GEMINI_API_KEY=...
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIM=768

# AI — Local LLM
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL_PRIMARY=qwen2.5:7b-instruct

# Auth
JWT_SECRET=...
JWT_ALGORITHM=HS256
JWT_EXPIRY_SECONDS=3600
NEXTAUTH_SECRET=...
NEXTAUTH_URL=http://localhost:3000

# Storage
STORAGE_DIR=./data/files

# Retrieval (Phase 3.1)
RERANKER_ENABLED=true
RERANKER_MODEL=BAAI/bge-reranker-base
BM25_TOP_K=50
VECTOR_TOP_K=50
RRF_K=60
RERANK_TOP_K=10
SEARCH_CACHE_TTL_SECONDS=300

# Ingestion limits (Phase 3.3)
AUDIO_MAX_UPLOAD_BYTES=524288000
ZIP_MAX_UPLOAD_BYTES=524288000
ZIP_MAX_FILES=50
NOTION_ACCESS_TOKEN=...   # optional — can also be passed per-request

# Logging
LOG_LEVEL=INFO
ENVIRONMENT=development
```

Keys from original specs **not present**: `OPENAI_API_KEY`, `S3_*`, `SENTRY_DSN_*`.

---

## 12. Tests — Actual State

| Test File | Status |
|---|---|
| `test_jwt.py` | ✓ |
| `test_chunking.py` | ✓ |
| `test_embedding.py` | ✓ |
| `test_llm.py` | ✓ |
| `test_auth.py` | ✓ integration |
| `test_ingest.py` | ✓ integration |
| `test_qa.py` | ✓ integration |
| `test_phase2_models.py` | ✓ |
| `tests/retrieval_eval.py` with `ranx` | **Not present** — eval harness deferred |

---

## 13. Completed Feature Summary (all phases)

### Phase 1
- User auth (register, login, JWT), document upload (PDF, TXT, MD), dedup
- Celery pipeline: parse → chunk → embed
- Vector search (cosine, HNSW), citation-grounded Q&A (Groq)
- Upload UI, Library, Q&A chat with citation chips

### Phase 2
- NER (spaCy + GLiNER), entity dedup, relation extraction (Ollama JSON)
- Knowledge graph: PostgreSQL adjacency, D3.js Graph Explorer
- Document intelligence: 3-level summaries, key insights, BERTopic tags, reading metrics
- Intelligence pane on document detail page

### Phase 2.5
- Claim extraction, claim embeddings (bge-base-en-v1.5)
- Contradiction detection: HNSW + DeBERTa NLI pipeline
- Credibility scoring: 4-signal composite + cohort recompute
- Conflicts page, CredibilityBadge in Library

### Phase 3.1 — Retrieval Foundation
- Migration 0008: `tsvector` column + GIN index + auto-update trigger on `chunks`
- BM25 query path, RRF fusion, `bge-reranker-base` CrossEncoder (lazy-load, env flag)
- Metadata filters: source_type, date_range, topic_tag, min_credibility, entity_id
- `POST /api/search` with Redis caching (5 min TTL, invalidated on ingest)
- `/search` page with filter sidebar, result cards, debounced input

### Phase 3.2 — Streaming + Conversation History
- SSE streaming on `POST /qa/stream` (token, citations, done, no_source events)
- Frontend EventSource integration via ReadableStream
- Conversation history endpoints (GET/PATCH/DELETE /api/conversations/{id})
- Collapsible conversation sidebar on Q&A page, rename/delete support
- Sliding-window message context passed to LLM

### Phase 3.3 — Multi-Source Ingestion
- `POST /api/ingest/url` — BeautifulSoup web scraping
- `POST /api/ingest/url-content` — pre-extracted content from browser extension
- `POST /api/ingest/audio` — Groq Whisper transcription
- `POST /api/ingest/youtube` — youtube-transcript-api
- `POST /api/ingest/notion` — notion-client SDK
- `POST /api/ingest/zip` — batch ZIP import (up to 50 files, path-traversal safe)
- SHA-256 dedup across all source types

### Phase 3.4 — Browser Extension
- Vite + MV3 extension at `extension/` — Chrome and Firefox compatible
- Content script: Readability.js page extraction, selection capture
- Background service worker: context menu ("Save selection"), SAVE_PAGE, SEARCH
- Popup: Search tab, Save tab, Settings tab (token storage)
- `GET /api/extension/token` + `POST /api/extension/token/rotate`
- `/connections` page in web app for token management + install instructions

### Phase 3.5 — Annotations
- Migration 0012: `annotations` table with highlight text, char positions, tags, color
- Full CRUD at `/api/annotations`, export to markdown/CSV
- `POST /api/notes/highlight` — browser extension selection endpoint (creates stub doc if URL is new)
- AnnotationPopover and AnnotationCard components, `/notes` page
- `user_insight` graph entity created by annotation worker
- Annotation text indexed as chunks with `source_type='user_annotation'`

### Phase 3.6 — Spaced Repetition
- Migration 0013: `flashcards` + `flashcard_reviews` tables
- SM-2 algorithm in `services/sm2.py` (0=again, 1=hard, 2=good, 3=easy)
- Card generation worker (Ollama, up to 3 cards per chunk, `cards` queue)
- Full card endpoints: generate, due, review, stats, edit, delete
- ReviewModal with CSS flip animation, keyboard shortcuts 1–4
- `/flashcards` page with stats dashboard (due today, streak, mastered, total)

### Phase 3.7 — Grafana
- 4 provisioned dashboard JSONs at `ops/grafana/dashboards/`:
  `ingestion.json`, `retrieval.json`, `ai_usage.json`, `system.json`

---

## 14. What Phase 4 Should Pick Up

1. **Collaboration / workspaces** — add `workspace_id` to all tables, RLS policies,
   real-time WebSocket activity feed. Deferred because it touches every row.

2. **Personal memory layer + recommendations** — logging infrastructure exists
   (Prometheus + structlog); a `user_events` table and recommendation engine can now
   be built on top of 3+ phases of usage data.

3. **Semantic alerts** — depends on personal memory layer (Phase 4 prerequisite).

4. **Research Assistant mode** — multi-step retrieval with hybrid search (now live)
   as the foundation. Agentic loop over the knowledge graph.

5. **Automation / rule engine** — event-driven triggers on ingest or Q&A.
   Notion sync (Celery beat) is the pattern to extend from.

6. **Retrieval eval harness** — `tests/retrieval_eval.py` with `ranx`, 30 hand-labelled
   query-chunk pairs, NDCG@10 + MRR@10 tracking. Deferred from Phase 3.

7. **FSRS scheduler** — replace SM-2 with the FSRS-4.5 algorithm for more accurate
   scheduling on dense decks.

8. **Playwright for JS-heavy sites** — Trafilatura covers 90% of articles; Playwright
   needed only for SPAs, paywalls, and infinite-scroll pages.
