# NexusMind — Phase 3 Plan
## Built on actual Phase 2.5 state · 100% free tier · No paid services

This plan replaces the original Phase 3 spec from the SourceWeave/NexusMind PDFs.
It accounts for what was actually built in Phases 1, 2, and 2.5 (per
`NexusMind_Phase2_5_Changes.md`), and substitutes every paid component (Cohere
Rerank, ElevenLabs, OpenAI APIs, AWS Textract, Sentry, etc.) with a free
alternative that fits the existing native-Windows + local-filesystem +
Ollama-local + Groq/Gemini-free-tier stack.

---

## 0. Constraints Carried Forward From Phase 2.5

These are non-negotiable for Phase 3 and shape every decision below:

- **No Docker.** Native Windows binaries only. PowerShell scripts to start
  services. Anything that requires Linux containers is out.
- **No cloud object storage.** Files live on local disk under `DATA_DIR`.
  Browser extension, audio, and Notion ingestion must write through the
  existing `StorageService`.
- **No paid AI APIs.** Embeddings are Gemini `text-embedding-004` (768-dim,
  free tier). Q&A LLM is Groq `llama-3.3-70b-versatile` (free tier). All other
  LLM work is Ollama `qwen2.5:7b-instruct` running locally.
- **No paid observability.** Logging is structlog JSON to stdout. Metrics are
  Prometheus at `/metrics`. Grafana is added in Phase 3 only as an
  open-source local install — not Grafana Cloud.
- **768-dim vectors everywhere on the chunk path.** The HNSW index is
  `vector(768)`. New retrieval code must respect this.
- **Single-user-per-account.** No `workspace_id` was added. Phase 3 keeps
  this; collaboration is deferred to Phase 4.

---

## 1. Phase 3 Scope at a Glance

Phase 3 has two halves. The first half closes the retrieval gap left open by
Phase 2. The second half delivers the four feature pillars from the original
Phase 3 spec — adapted to the actual stack and the free-only constraint.

| # | Track | Pillar | Status |
|---|---|---|---|
| A | Foundation (Phase 2 deferred) | Hybrid retrieval + reranker | Carry-over |
| B | Foundation (Phase 2 deferred) | Metadata filters + Search page | Carry-over |
| C | Foundation (Phase 2 deferred) | SSE streaming + conversation history UI | Carry-over |
| D | Phase 3 main | Multi-source ingestion (web, OCR, audio, YouTube, Notion) | New |
| E | Phase 3 main | Browser extension (Chrome MV3 + Firefox via polyfill) | New |
| F | Phase 3 main | Notes & annotation system (graph-integrated) | New |
| G | Phase 3 main | Spaced repetition (SM-2, Ollama-generated cards) | New |
| H | Phase 3 ops | Grafana dashboard pointing at existing `/metrics` | New |

Track A–C must ship before D–G. Retrieval quality is the foundation everything
else relies on, and the missing search page is a P1 paper cut.

---

## 2. Track A — Hybrid Retrieval + Local Reranker

### 2.1 Why this is Phase 3, not Phase 4

Phase 2.5 left retrieval at "vector-only cosine similarity." Q&A quality, the
new search page, semantic alerts, contradiction-candidate generation, and the
spaced repetition card generator all consume retrieval output. Improving it
once propagates everywhere downstream.

### 2.2 BM25 via PostgreSQL `tsvector`

Free, no new dependency, plays well with the existing pgvector setup.

**Migration `0008_chunk_tsvector`:**
- Add `tsv tsvector` column on `chunks`
- Backfill: `UPDATE chunks SET tsv = to_tsvector('english', coalesce(text, ''))`
- Create GIN index: `CREATE INDEX chunks_tsv_gin ON chunks USING GIN(tsv)`
- Add trigger so `tsv` updates on `INSERT`/`UPDATE`:
  ```sql
  CREATE TRIGGER chunks_tsv_update BEFORE INSERT OR UPDATE
  ON chunks FOR EACH ROW EXECUTE FUNCTION
  tsvector_update_trigger(tsv, 'pg_catalog.english', text);
  ```

**Query at runtime:**
```sql
SELECT id, ts_rank_cd(tsv, plainto_tsquery('english', :q)) AS bm25_score
FROM chunks
WHERE tsv @@ plainto_tsquery('english', :q) AND user_id = :uid
ORDER BY bm25_score DESC LIMIT 50;
```

### 2.3 Reciprocal Rank Fusion

The Phase 2 spec called for RRF; the implementation never landed. Drop it into
`services/retrieval.py` as a pure Python helper — no library needed.

```python
def rrf_merge(rank_lists: list[list[int]], k: int = 60) -> list[int]:
    scores = {}
    for ranks in rank_lists:
        for pos, chunk_id in enumerate(ranks):
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (k + pos + 1)
    return [cid for cid, _ in sorted(scores.items(), key=lambda x: -x[1])]
```

Pipeline: take top-50 from vector search, top-50 from BM25, RRF-merge to top-30,
then rerank to top-10.

### 2.4 Local Reranker — `BAAI/bge-reranker-base`

The spec called for Cohere Rerank v3, which is paid past a small free tier.
Swap for the local equivalent:

| Aspect | Choice |
|---|---|
| Model | `BAAI/bge-reranker-base` (~110M params) |
| Loader | `sentence-transformers` `CrossEncoder` |
| Runs on | CPU (300-600ms for 30 pairs); GPU optional |
| License | MIT — free for commercial use |
| Memory | ~500MB RAM |

```python
from sentence_transformers import CrossEncoder
_reranker = CrossEncoder("BAAI/bge-reranker-base", max_length=512)

def rerank(query: str, chunks: list[Chunk], top_k: int = 10) -> list[Chunk]:
    pairs = [(query, c.text) for c in chunks]
    scores = _reranker.predict(pairs, batch_size=16, show_progress_bar=False)
    ranked = sorted(zip(chunks, scores), key=lambda x: -x[1])
    return [c for c, _ in ranked[:top_k]]
```

Lazy-load on first call so the API process doesn't pay the cost at startup.
Add a `RERANKER_ENABLED` env var so it can be turned off on machines with
< 8GB RAM.

### 2.5 New Retrieval Flow

```
query → embed (Gemini 768-d)        →┐
        BM25 tsvector top-50        →┼→ RRF merge top-30 → bge-reranker → top-10 → LLM
                                     ┘
```

### 2.6 Acceptance

- `tests/test_hybrid_retrieval.py` covering BM25 path, RRF function, and
  reranker call (mocked or with a small fixture model).
- New `tests/retrieval_eval.py` using `ranx` (free, MIT) with ~30 hand-labelled
  query-chunk relevance pairs. Track NDCG@10 and MRR@10 over time.
- Q&A endpoint latency p95 < 4s with reranker enabled, < 2.5s without.

---

## 3. Track B — Metadata Filters + Search Page

### 3.1 Filter Surface

All four already exist in the data model thanks to Phase 2.5; they just aren't
exposed:

| Filter | Backing Column | Source |
|---|---|---|
| `source_type` | `documents.source_type` | Phase 1 |
| `date_range` | `documents.uploaded_at` | Phase 1 |
| `topic_tag` | `document_intelligence.topics[]` (JSONB) | Phase 2 |
| `min_credibility` | `documents.credibility_score` | Phase 2.5 |
| `entity_id` | join via `entities` → chunks (already present) | Phase 2 |

Filters apply at the SQL level inside both vector and BM25 candidate stages,
before fusion — not after — so we don't lose recall.

### 3.2 New Routes

- `POST /api/search` — body: `{ query, filters, top_k }`, returns ranked chunk
  list with document context and credibility badge.
- `POST /qa` — extend with `filters` field; same shape as `/api/search`.

Note the mixed prefix: `/api/search` follows the Phase 2 convention even though
`/qa` is unprefixed (Phase 1 legacy). Don't break either.

### 3.3 Search Page — `/search`

The page that was specced in Phase 1 but never built. Now warranted because we
finally have something worth searching beyond Q&A.

- Tailwind + TanStack Query result cards
- Snippet highlighting with `mark.js` (free, MIT)
- Filter sidebar: source type chips, date-range picker, topic multi-select,
  credibility slider
- Result card shows: title, snippet, page, credibility badge (reuse
  `CredibilityBadge.tsx`), score
- Click result → open `/library/[id]` scrolled to the chunk
- Debounced input (300ms), URL-state filters so search is shareable

### 3.4 Result Caching

Redis is already running for Celery; reuse it.

- Cache key: SHA-256(`q || sorted(filters) || top_k`)
- TTL: 5 minutes
- Invalidate the entire prefix when ingestion completes a new document — coarse
  but correct, and ingestion is rare relative to search

---

## 4. Track C — SSE Streaming + Conversation History

### 4.1 Server-Sent Events for `/qa`

The Groq client supports streaming via the OpenAI-compatible API; the existing
`services/llm.py` just needs a streaming wrapper. Use FastAPI's
`StreamingResponse` and `text/event-stream` content type — no external library
needed.

```python
async def qa_stream(request: QaRequest) -> StreamingResponse:
    async def gen():
        retrieved = await retrieve(request.query, request.filters)
        if not retrieved or max_sim(retrieved) < QA_NO_SOURCE_THRESHOLD:
            yield 'event: no_source\ndata: {}\n\n'
            return
        async for token in llm.stream(prompt(retrieved, request.query)):
            yield f'event: token\ndata: {json.dumps({"t": token})}\n\n'
        yield f'event: citations\ndata: {json.dumps(citations)}\n\n'
        yield 'event: done\ndata: {}\n\n'
    return StreamingResponse(gen(), media_type='text/event-stream')
```

Citations are sent as a final event after the stream completes, because they
require chunk-id resolution against the full answer text.

Frontend: use native `EventSource` (no library). Existing Q&A component just
swaps `fetch` for `new EventSource(...)` and appends tokens as they arrive.

### 4.2 Conversation History UI

Messages already persist to the `messages` table from Phase 1; only the UI is
missing.

- New route: `GET /api/conversations` (list user's conversations, paginated)
- New route: `GET /api/conversations/{id}` (full message thread)
- New route: `DELETE /api/conversations/{id}`
- New route: `PATCH /api/conversations/{id}` (rename)
- Frontend: collapsible left sidebar on `/qa` page, new-conversation button,
  click conversation → load messages and continue the thread
- Sliding-window memory: send the last N=6 messages as context to the LLM along
  with retrieved chunks

---

## 5. Track D — Multi-Source Ingestion

The original Phase 3 spec lists web URLs, OCR, audio, Notion, and YouTube.
Every option in the original spec had at least one paid alternative; below is
the free path for each.

### 5.1 Web URL Ingestion

| Component | Spec choice | Free choice for Phase 3 |
|---|---|---|
| HTTP client | `httpx` | `httpx` ✓ already in stack |
| Content extraction | Playwright (heavy) | **Trafilatura** (pure Python, MIT) |
| Fallback for JS-heavy pages | Playwright | Defer to Phase 4 — Trafilatura covers 90%+ of articles |
| Metadata | Custom | Trafilatura's built-in `extract_metadata` |

```python
import httpx, trafilatura
async def fetch_url(url: str) -> ParsedDocument:
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
        resp = await c.get(url, headers={"User-Agent": "NexusMind/1.0"})
    extracted = trafilatura.extract(resp.text, include_links=True,
                                    include_tables=True, output_format='txt')
    metadata = trafilatura.extract_metadata(resp.text)
    return ParsedDocument(text=extracted, title=metadata.title,
                          author=metadata.author, date=metadata.date)
```

**API:** `POST /ingest/url` body `{ url }` — enqueue Celery job same as upload,
writes a stub file to `DATA_DIR` containing the cleaned text (so the storage
contract is uniform).

**Edge cases handled in MVP:**
- Redirects (already in httpx)
- Encoding detection (Trafilatura)
- Content too short (< 200 chars) → reject with explanation
- Already-ingested URL (SHA-256 of canonical URL) → dedupe like uploads

**Deferred:** Playwright for SPAs (paywall, infinite scroll) — not free in
maintenance cost. Revisit only if real usage shows a gap.

### 5.2 OCR for Scanned PDFs

`services/ocr.py` already exists. Phase 3 wires it into the pipeline.

Decision tree per PDF in the parse worker:
1. Run `pypdf` text extraction.
2. If < 100 characters per page on average → it's scanned, send through OCR.
3. OCR via **Tesseract 5** (free, Apache 2.0). Use `pytesseract` Python
   bindings. Tesseract binary is `winget install tesseract` on Windows.
4. Pre-process pages: `Pillow` for grayscale + threshold + deskew (free).
5. New Celery queue `ocr` so slow OCR doesn't block the `default` queue.

`AWS Textract` from the original spec is paid → never. For handwriting or
complex tables, accept lower quality at Phase 3 and flag the document in the
intelligence pane as "OCR quality: low" rather than reach for a cloud service.

### 5.3 Audio Transcription

| Spec | Phase 3 free choice |
|---|---|
| OpenAI Whisper API (paid) | **`faster-whisper`** with `base.en` or `small.en` model |
| ElevenLabs | N/A — only needed for reel TTS in Phase 5 |

`faster-whisper` runs Whisper via CTranslate2 — 4x faster than the reference
implementation, runs CPU-only, MIT license. Models auto-download from
HuggingFace on first use.

```python
from faster_whisper import WhisperModel
model = WhisperModel("base.en", device="cpu", compute_type="int8")

def transcribe(audio_path: str) -> list[Segment]:
    segments, _ = model.transcribe(audio_path, beam_size=5, vad_filter=True)
    return [Segment(start=s.start, end=s.end, text=s.text) for s in segments]
```

**Pipeline:**
- New MIME types accepted: `audio/mpeg`, `audio/wav`, `audio/m4a`,
  `audio/ogg`, `video/mp4` (audio track only — extract with `ffmpeg`,
  which is free)
- New queue: `transcription`
- After transcription, the text + segment timestamps flow into the standard
  parse → chunk → embed pipeline, with timestamps preserved as chunk metadata
  so citations can show "at 03:42 in the recording"
- Limit audio file size to 500MB; reject longer with a clear error

**ffmpeg** is GPL/LGPL. The Windows static build is free; users install via
`winget install ffmpeg`.

### 5.4 YouTube Transcripts

`youtube-transcript-api` (free, MIT) pulls captions from YouTube without
downloading the video.

- New route: `POST /ingest/youtube` body `{ url }`
- Worker fetches transcript (English priority, auto-generated fallback),
  stitches segments, captures video metadata via `yt-dlp` (free, Unlicense) for
  title/channel/upload-date
- Goes through standard pipeline as a text document with timestamp metadata
- If no transcript available → fallback to audio download (`yt-dlp` extracts
  audio) → faster-whisper transcription. Both legs are free.

### 5.5 Notion Connector

Notion's API is free for personal use. Use the official `notion-client` Python
SDK (free, MIT).

- User adds a Notion integration token in Settings page (manual paste — full
  OAuth flow requires app verification and is deferred)
- New route: `POST /notion/sync` — sync now
- New route: `POST /notion/schedule` — sync every N hours (Celery beat)
- Worker iterates databases the integration has access to, pulls page blocks,
  converts to Markdown via `notion-to-md` (free), routes through standard
  ingestion
- Idempotency via Notion page ID + `last_edited_time` — only re-ingest changed
  pages

### 5.6 Bulk ZIP Import

Lightweight, useful for power users importing existing archives.

- `POST /ingest/zip` accepts a zip up to `MAX_UPLOAD_BYTES`
- Worker validates entries (path traversal check, MIME whitelist), extracts to
  a temp dir, enqueues one ingestion job per supported file inside
- Skips entries that fail the MIME whitelist with a warning back to the UI

---

## 6. Track E — Browser Extension

### 6.1 Stack — All Free

| Component | Choice |
|---|---|
| Manifest | Manifest V3 (Chrome and Firefox-compatible with `webextension-polyfill`) |
| Build tool | **Vite** + `vite-plugin-web-extension` (free, MIT) |
| Content extraction | **Readability.js** from Mozilla (free, Apache 2.0) |
| Popup UI | React + Tailwind, bundled with Vite |
| Auth | JWT pasted from web app's settings page |

No Chrome Web Store submission required for personal use — load unpacked.
Submission is also free (one-time $5 developer registration is the only cost,
which is optional for sideloading).

### 6.2 Features (MVP)

1. **Save Full Page** — toolbar button. Runs Readability.js in content script,
   POSTs `{ url, title, content_html, captured_at }` to `/ingest/url-content`
   (new endpoint that accepts pre-extracted content, distinct from
   `/ingest/url` which fetches server-side).
2. **Save Selection** — right-click context menu on selected text. POSTs the
   highlighted snippet plus 1-2 sentences of surrounding context as a tagged
   note → becomes a `user_insight` entity linked to the source document.
3. **Quick search** — popup has a search box that hits `/api/search` and shows
   recent results without leaving the page.
4. **Auth flow** — Settings page in the web app exposes a per-extension token
   (long-lived JWT, scoped to the ingest and search endpoints). User copies it
   into the extension popup once. Stored in `chrome.storage.local`. Token can
   be revoked from settings.

### 6.3 Endpoints

- `POST /ingest/url-content` — accepts pre-extracted HTML/text; useful when the
  extension already ran Readability on the live page
- `POST /api/notes/highlight` — creates a `user_insight` annotation tied to the
  source URL (creating a stub Document record if the URL is new)
- `GET /api/extension/token` (web app only) — issues an extension-scoped JWT

### 6.4 Acceptance

- Save a random article → appears in Library within 15 seconds with extracted
  text and metadata
- Right-click highlight on a Wikipedia paragraph → appears in `/notes` page
  (Track F) linked to the source URL
- Quick search popup returns results without opening the web app

---

## 7. Track F — Notes & Annotation System

### 7.1 Data Model

**Migration `0010_annotations`:**

```sql
CREATE TABLE annotations (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id     UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_id        UUID REFERENCES chunks(id) ON DELETE SET NULL,
    highlight_text  TEXT NOT NULL,
    char_start      INTEGER,
    char_end        INTEGER,
    note            TEXT,
    tags            TEXT[],
    color           TEXT DEFAULT 'yellow',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX annotations_user_doc ON annotations(user_id, document_id);
CREATE INDEX annotations_user_chunk ON annotations(user_id, chunk_id);
CREATE INDEX annotations_tags_gin ON annotations USING GIN(tags);
```

### 7.2 Graph Integration — `user_insight` Entity Type

The graph schema already has `entities` and `entity_edges`. Add a new entity
`type` value: `user_insight`. When the user attaches a note (not just a
highlight), a worker creates a `user_insight` entity:

- Node `text` = the note body
- Embed via `all-MiniLM-L6-v2` (already in stack for entity dedup)
- Edge to source chunk's entities via `relates_to` with confidence = 1.0
- These nodes are visible in the Graph Explorer with a distinct color/icon

This makes user-contributed knowledge first-class — searchable, traversable,
and retrievable in Q&A context — without changing the storage layer.

### 7.3 Annotations in Retrieval

Index annotation text (highlight + note) as chunks in the vector store with
`source_type='user_annotation'`. They show up in `/qa` and `/search` results
and can be filtered by the source-type chip.

### 7.4 Frontend

- **Annotation overlay** on `/library/[id]` document viewer. Use
  `window.getSelection()` and `Range.getBoundingClientRect()` to position a
  popover. No heavy editor library needed; the Tiptap option in the spec is
  overkill for this MVP.
- **`/notes` page** — list view of all annotations, filter by tag, document,
  date. Click → jump to source.
- **Export** — `GET /api/annotations/export?format=md|csv` returns all
  annotations as markdown or CSV.

### 7.5 Endpoints

- `POST /api/annotations` — create
- `GET /api/annotations` — list, filterable by `?document_id`, `?tag`,
  `?from`, `?to`
- `PATCH /api/annotations/{id}` — edit note or tags
- `DELETE /api/annotations/{id}`
- `GET /api/annotations/export?format=md|csv`

---

## 8. Track G — Spaced Repetition System

### 8.1 Card Generation — Free via Ollama

Use the local Ollama `qwen2.5:7b-instruct` (already in stack) — no paid API.
JSON-mode prompts already work for claim extraction in Phase 2.5; this is a
parallel use of the same client.

```python
PROMPT = """You will receive a document chunk. Generate up to 3 flashcards.
Each card has a clear question and a short, specific answer that comes
directly from the chunk. Return JSON: { "cards": [{ "q": "...", "a": "..." }] }.
Skip generation if the chunk is not factual content."""
```

Trigger: after `intelligence` worker finishes for a document, optionally run a
`cards` worker (off by default; user enables per-document or globally in
settings to avoid generating cards from chunks they don't care about).

### 8.2 Scheduling — SM-2

Classic, transparent, zero dependencies. Plain Python.

```python
def sm2(card_state: CardState, rating: int) -> CardState:
    # rating: 0=again, 1=hard, 2=good, 3=easy
    q = rating + 2  # SM-2 expects 0..5
    if q < 3:
        return card_state._replace(reps=0, interval=1, due=today() + 1)
    if card_state.reps == 0:
        interval = 1
    elif card_state.reps == 1:
        interval = 6
    else:
        interval = round(card_state.interval * card_state.ease)
    ease = max(1.3, card_state.ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)))
    return CardState(reps=card_state.reps + 1, interval=interval, ease=ease,
                     due=today() + interval)
```

(`FSRS` was the spec's alternative; SM-2 is simpler, sufficient, and has no
external library dependency. FSRS can be a Phase 4 upgrade if the user wants
better scheduling on dense decks.)

### 8.3 Data Model — Migration `0011_flashcards`

```sql
CREATE TABLE flashcards (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chunk_id        UUID REFERENCES chunks(id) ON DELETE SET NULL,
    document_id     UUID REFERENCES documents(id) ON DELETE SET NULL,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    reps            INTEGER DEFAULT 0,
    interval_days   INTEGER DEFAULT 0,
    ease            FLOAT DEFAULT 2.5,
    due_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    suspended       BOOLEAN DEFAULT FALSE
);
CREATE INDEX cards_user_due ON flashcards(user_id, due_date) WHERE NOT suspended;

CREATE TABLE flashcard_reviews (
    id           UUID PRIMARY KEY,
    card_id      UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    rating       SMALLINT NOT NULL,  -- 0..3
    reviewed_at  TIMESTAMPTZ DEFAULT now()
);
```

### 8.4 Endpoints

- `POST /api/cards/generate` body `{ document_id }` — kick off generation
- `GET /api/cards/due` — cards due today or earlier
- `POST /api/cards/{id}/review` body `{ rating }` — applies SM-2, returns next
  due date
- `PATCH /api/cards/{id}` — edit Q/A or suspend
- `DELETE /api/cards/{id}`
- `GET /api/cards/stats` — streak, mastery (% of cards with reps ≥ 3),
  due-today count

### 8.5 Frontend

- **`/flashcards` page** — shows due count, "Start review" button, recent
  activity chart
- **Review modal** — flip animation via CSS 3D transform (no library), four
  rating buttons (Again / Hard / Good / Easy) with keyboard shortcuts 1-4
- **Per-document panel** — on `/library/[id]`, show generated cards for that
  document with edit/delete
- **Browser notifications** — Web Notifications API (no library); user opts in,
  service worker checks `/api/cards/due` at app load and at a 1-hour interval

### 8.6 Worker Queue

New Celery queue `cards`:

```powershell
celery -A app.workers.celery_app worker --pool=solo `
  --queues=default,ner,intelligence,claims,nli,credibility,ocr,transcription,cards
```

(Add `ocr`, `transcription`, and `cards` to the existing six queues from Phase
2.5.)

---

## 9. Track H — Grafana Dashboard

Prometheus is already exporting metrics at `/metrics`. The original Phase 2
spec named Grafana but it was never installed.

- **Grafana OSS** is free under AGPL — install the Windows binary, run as a
  service
- Configure Prometheus data source pointing at `http://localhost:9090`
- Provision dashboards via JSON (committed to repo at
  `ops/grafana/dashboards/`):
  - `ingestion.json`: queue depth per queue, task duration histograms, task
    failure rate, dead-letter queue size
  - `retrieval.json`: query latency p50/p95/p99, BM25 vs vector vs reranker
    timings, cache hit rate
  - `ai_costs.json`: Groq tokens/day (free tier limits), Gemini embedding
    requests/day, Ollama request count and average latency
  - `system.json`: CPU, memory, disk usage on `DATA_DIR`

No Sentry, no GlitchTip, no PagerDuty — those were paid-or-complex. Phase 3
ships structured logs + Prometheus + Grafana, which is enough for a personal
project.

---

## 10. Free-Tier Tech Stack Summary

Every component below is either free-tier API, MIT/Apache/BSD-licensed
open source, or already in the Phase 2.5 stack.

| Layer | Component | License / Tier |
|---|---|---|
| BM25 | PostgreSQL `tsvector` + GIN | Open source (PostgreSQL license) |
| Vector | pgvector | PostgreSQL extension, open source |
| Reranker | `BAAI/bge-reranker-base` via `sentence-transformers` | MIT |
| LLM (Q&A) | Groq `llama-3.3-70b-versatile` | Free tier (existing) |
| LLM (local) | Ollama `qwen2.5:7b-instruct` | Apache 2.0 (existing) |
| Embeddings (chunks) | Gemini `text-embedding-004` | Free tier (existing) |
| Embeddings (entities) | `all-MiniLM-L6-v2` | Apache 2.0 (existing) |
| Embeddings (claims) | `BAAI/bge-base-en-v1.5` | MIT (existing) |
| Web extraction | Trafilatura | Apache 2.0 |
| OCR | Tesseract 5 | Apache 2.0 |
| Audio ASR | `faster-whisper` (`base.en`) | MIT |
| Video tooling | ffmpeg, yt-dlp | LGPL / Unlicense |
| YouTube transcripts | `youtube-transcript-api` | MIT |
| Notion | `notion-client` Python SDK | MIT |
| Eval | `ranx` | MIT |
| Browser extension | Vite + Readability.js + webextension-polyfill | MIT / Apache 2.0 / MIT |
| SRS | Custom SM-2 implementation | N/A — own code |
| Annotations | Native `window.getSelection` API | N/A — browser standard |
| Observability | Prometheus + Grafana OSS + structlog | Apache 2.0 / AGPL / MIT |

---

## 11. Database Migrations Summary

In sub-phase execution order (numbers reflect actual run order, not original plan):

1. `0008_chunk_tsvector` — add `tsv` column + GIN index + trigger on `chunks` *(3.1)*
2. `0009_url_documents` — extend `documents` with `source_url`, `captured_at`,
   `extension_capture` (boolean), `media_type` (audio/video/text/notion) *(3.3)*
3. `0010_notion_state` — `notion_integrations` (user_id, token_encrypted,
   workspace_name) + `notion_pages` (page_id, last_synced_at,
   notion_last_edited_at, document_id) *(3.3)*
4. `0011_audio_segments` — `audio_segments` (chunk_id, start_seconds,
   end_seconds) for timestamped citations *(3.3)*
5. `0012_annotations` — annotations table (see § 7.1) *(3.5)*
6. `0013_flashcards` — flashcards + flashcard_reviews tables (see § 8.3) *(3.6)*

Numbers match sub-phase order (3.1 → 3.3 → 3.5 → 3.6) so Alembic file names
stay sequential. All reversible. Use Alembic `downgrade` consistently.

---

## 12. New API Routes Summary

Following the existing mixed-prefix scheme (Phase 1 routes unprefixed, Phase
2+ routes under `/api`):

| Track | Route | Method | Purpose |
|---|---|---|---|
| A | `/api/search` | POST | Hybrid search with filters |
| C | `/qa/stream` | POST | Streaming Q&A (fetch ReadableStream — EventSource cannot send Authorization headers) |
| C | `/api/conversations` | GET, POST | List, create conversation |
| C | `/api/conversations/{id}` | GET, PATCH, DELETE | Detail, rename, delete |
| D | `/ingest/url` | POST | Server-side URL fetch + ingest |
| D | `/ingest/url-content` | POST | Pre-extracted content from extension |
| D | `/ingest/audio` | POST | Audio file upload |
| D | `/ingest/youtube` | POST | YouTube URL ingest |
| D | `/ingest/zip` | POST | Bulk archive import |
| D | `/notion/connect` | POST | Save integration token |
| D | `/notion/sync` | POST | Sync now |
| D | `/notion/schedule` | POST | Set recurring sync |
| E | `/api/extension/token` | GET | Issue scoped JWT |
| F | `/api/annotations` | GET, POST | List, create |
| F | `/api/annotations/{id}` | PATCH, DELETE | Edit, delete |
| F | `/api/annotations/export` | GET | Markdown/CSV export |
| G | `/api/cards/generate` | POST | Kick off generation |
| G | `/api/cards/due` | GET | Due-today list |
| G | `/api/cards/{id}/review` | POST | Submit SM-2 rating |
| G | `/api/cards/{id}` | PATCH, DELETE | Edit, delete |
| G | `/api/cards/stats` | GET | Streak, mastery |

---

## 13. New Worker Queues

Total queues after Phase 3: **nine.**

```powershell
celery -A app.workers.celery_app worker --pool=solo `
  --queues=default,ner,intelligence,claims,nli,credibility,ocr,transcription,cards
```

| Queue | Existing? | Tasks |
|---|---|---|
| `default` | ✓ | parse, chunk, embed |
| `ner` | ✓ | extract_entities, extract_relations |
| `intelligence` | ✓ | generate_intelligence, assign_topics |
| `claims` | ✓ | extract_claims |
| `nli` | ✓ | detect_contradictions |
| `credibility` | ✓ | compute_credibility, recompute_cohort |
| `ocr` | New | run_tesseract, ocr_preprocess |
| `transcription` | New | transcribe_audio, fetch_youtube_transcript |
| `cards` | New | generate_cards |

Notion sync is a Celery beat job, not a queue, scheduled at user-configured
intervals.

---

## 14. New Frontend Pages & Components

### New pages
- `/search` (Track B)
- `/notes` (Track F)
- `/flashcards` (Track G)
- `/connections` (Track D + E — Notion token, extension token, RSS feeds)

### New top-level components (under `components/`)
- `search/SearchBar.tsx`, `search/ResultCard.tsx`, `search/FilterPanel.tsx`
- `qa/ConversationSidebar.tsx`, `qa/StreamingMessage.tsx`
- `ingest/UrlImport.tsx`, `ingest/AudioUpload.tsx`,
  `ingest/YouTubeImport.tsx`, `ingest/NotionConnect.tsx`,
  `ingest/ZipImport.tsx`
- `annotations/HighlightOverlay.tsx`, `annotations/AnnotationPopover.tsx`,
  `annotations/AnnotationCard.tsx`
- `cards/ReviewModal.tsx`, `cards/CardEditor.tsx`, `cards/DueBadge.tsx`

### New hooks
- `useSearch.ts`, `useStreamingQa.ts`, `useConversations.ts`,
  `useAnnotations.ts`, `useFlashcards.ts`, `useNotionSync.ts`

### Service clients
- `services/search.ts`, `services/annotations.ts`, `services/flashcards.ts`,
  `services/ingest.ts`, `services/notion.ts`

### Navigation update
`app/(app)/layout.tsx` adds links: **Search**, **Notes**, **Flashcards**,
**Connections** alongside existing Library, Graph, Conflicts, Q&A.

---

## 15. Implementation Order

Six sub-phases, each independently shippable. Don't start the next until the
prior is testable end-to-end.

### Phase 3.1 — Retrieval Foundation (Tracks A + B)
- Migration 0008 (tsvector + GIN)
- BM25 query path in `services/retrieval.py`
- RRF fusion helper
- bge-reranker-base integration with lazy load and on/off env flag
- Metadata filters in `/qa` and new `/api/search`
- Search page UI + filter sidebar
- Retrieval eval harness with `ranx`
- **Done when:** NDCG@10 on the eval set improves by ≥ 10% vs. vector-only,
  and `/search` returns filtered results in < 800ms p95.

### Phase 3.2 — Streaming + History (Track C)
- SSE wrapper on Groq client
- `/qa/stream` endpoint
- Frontend EventSource integration
- Conversation history endpoints + sidebar UI
- Sliding-window memory in prompt assembly
- **Done when:** First token visible in UI within 600ms; conversations
  persist across reloads; renaming and deleting works.

### Phase 3.3 — Multi-Source Ingestion (Track D)
- Migrations 0009, 0012, 0013
- Trafilatura URL worker + `/ingest/url`
- OCR wiring: parse worker decision tree + `ocr` queue
- `faster-whisper` worker + `transcription` queue + `/ingest/audio`
- YouTube transcript worker + audio fallback
- Notion token storage + sync worker + Celery beat schedule
- Bulk ZIP import
- **Done when:** All five source types ingest a representative sample, dedupe
  works for each, and timestamped citations show for audio + YouTube.

### Phase 3.4 — Browser Extension (Track E)
- Vite + MV3 scaffold
- Readability.js content script
- Save-page and save-selection flows
- Popup quick search
- Extension token issuance endpoint + settings UI in web app
- Manual install instructions in README
- **Done when:** Loads unpacked in Chrome and Firefox; all three actions
  round-trip successfully; token revocation works.

### Phase 3.5 — Annotations (Track F)
- Migration 0010
- Annotation CRUD + export endpoints
- HighlightOverlay component on document viewer
- `/notes` page
- `user_insight` graph entity creation worker
- Annotation indexing into vector store with `source_type='user_annotation'`
- **Done when:** Highlights persist across reloads, appear in graph, surface
  in Q&A retrieval, export to markdown.

### Phase 3.6 — Spaced Repetition (Track G)
- Migration 0011
- Card generation worker (`cards` queue)
- SM-2 implementation + tests
- Card endpoints
- Review modal + keyboard shortcuts
- `/flashcards` dashboard
- Browser notifications via service worker
- **Done when:** Cards generate for a document, due-today list populates,
  SM-2 schedules cards correctly across all four ratings (verified by unit
  test).

### Phase 3.7 — Observability Polish (Track H, runs in parallel with any of the above)
- Grafana OSS install + Windows service
- Four provisioned dashboards
- README section on viewing metrics
- **Done when:** Dashboards render with live data from a 24-hour activity
  window.

---

## 16. Acceptance Criteria for Phase 3 as a Whole

- ✅ Hybrid retrieval (BM25 + vector + RRF + bge-reranker) is the default path
- ✅ Search page exists, filters work end-to-end, results cache for 5 min
- ✅ Q&A streams tokens via SSE; conversation history persists and is
  browsable
- ✅ Ingestion supports: PDF, TXT, MD, web URL, audio file, YouTube URL,
  Notion page, ZIP archive — with appropriate dedupe per source type
- ✅ Browser extension installs unpacked in Chrome and Firefox; save-page and
  save-selection flows complete in under 5 seconds
- ✅ Annotations persist, render inline, appear as `user_insight` graph
  entities, are retrievable in Q&A, and exportable
- ✅ Spaced repetition: cards generate on demand, due-today endpoint works,
  SM-2 scheduling is unit-tested for all four ratings
- ✅ Grafana dashboards exist for ingestion, retrieval, AI usage, and system
  metrics
- ✅ No paid service has been added (Groq stays free tier, Gemini stays free
  tier, everything else is local or OSS)
- ✅ All new tests pass; retrieval NDCG@10 improves on eval set; pipeline
  end-to-end test green

---

## 17. What's Explicitly Deferred to Phase 4

These were tempting to fold into Phase 3 but don't fit the "free + native +
single-user" envelope, or aren't foundational for Phase 5:

- **Collaboration / workspaces** — needs `workspace_id` migration touching
  every row, RLS policies, real-time WebSocket activity feed. Big lift, no
  retrieval benefit. → Phase 4.
- **Personal memory layer & recommendations** — needs 2-4 weeks of usage data
  to be meaningful per the original roadmap. Logging infrastructure can ship
  in Phase 3 (just add a `user_events` table); surfacing recommendations is
  Phase 4.
- **Semantic alerts** — depends on personal memory layer.
- **Automation workflows (rule engine)** — depends on stable event hooks and
  Notion-style triggers. Notion sync as a scheduled job in Phase 3 covers the
  most common case.
- **Playwright for JS-heavy sites** — Trafilatura covers 90%+; revisit only
  if users hit a real gap.
- **FSRS scheduler** — SM-2 is sufficient for MVP-volume decks.
- **Research Assistant mode** — its retrieval quality depends on hybrid +
  reranker being live (Track A), which is exactly what Phase 3 unlocks.
  Build in Phase 4 on top of solid retrieval.

---

## 18. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `faster-whisper` model download fails on first ingest | Medium | Pre-download on first worker boot; show clear error to user |
| Tesseract install missing on user's Windows machine | High | Detect at startup, log a clear warning, gracefully fall back to text-only extraction with a "OCR unavailable" flag on the document |
| bge-reranker-base RAM pressure on 8GB machines | Medium | `RERANKER_ENABLED=false` env flag; graceful fallback to RRF-only top-10 |
| Groq free-tier rate limit hit during ingestion + Q&A burst | Medium | Already-existing retry logic; consider routing claim extraction fully to Ollama to save Groq budget for user-facing Q&A |
| Notion API rate limits during initial sync of a large workspace | Low | Use Notion's documented pagination; sleep 350ms between page fetches (per their best practice) |
| Browser extension token leak | Low | Scope JWT to specific endpoints; allow revocation from settings; rotate on demand |
| SSE proxy buffering by intermediate layers | Low (localhost dev) | Set `X-Accel-Buffering: no` header; document if reverse proxy is added later |

---

## 19. Out of Scope for Phase 3 (Explicit)

So nothing scope-creeps in:

- Reels / short-form video generation (Phase 5)
- Meme generator (Phase 5)
- TTS of any kind (Phase 5 dependency)
- Image generation (Phase 5 — was DALL-E 3, paid; Stable Diffusion local is
  possible but a Phase 5 problem)
- Mobile app
- Public sharing / collaboration
- Multi-tenancy
- Docker / cloud deployment (separate Supabase migration plan exists)

---

## 20. Estimated Effort

Rough order-of-magnitude only. Solo developer, focused work:

| Sub-phase | Estimate |
|---|---|
| 3.1 Retrieval foundation | 5-7 days |
| 3.2 Streaming + history | 2-3 days |
| 3.3 Multi-source ingestion | 7-10 days |
| 3.4 Browser extension | 4-5 days |
| 3.5 Annotations | 4-5 days |
| 3.6 Spaced repetition | 3-4 days |
| 3.7 Grafana | 1-2 days |
| **Total** | **~26-36 days** of focused work |

Tracks 3.4 (extension) and 3.7 (Grafana) can run in parallel with others. 3.5
and 3.6 can be reordered based on what feels more motivating to ship first.

---

*End of Phase 3 Plan*
