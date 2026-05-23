# NexusMind — Phase 3 Single Build Prompt
## Paste this once at the start of Phase 3. Everything is in here.

---

## PART 0 — ORIENTATION (do this before any code)

You are working on **NexusMind**, a personal AI knowledge graph system built with
FastAPI + Celery + PostgreSQL/pgvector + Next.js. Phases 1, 2, and 2.5 are
complete. You are now implementing Phase 3.

### Step 1 — Read the state-of-the-world docs

Read these files in order:

1. **`NexusMind_Phase2_5_Changes.md`** (project root). This is the authoritative
   description of what was actually built. The original PDF specs differ
   significantly. Key sections:
   - §1: No Docker, local filesystem storage, no MinIO/S3
   - §2: Gemini 768-dim embeddings, Groq llama-3.3-70b, Ollama qwen2.5 —
     NOT OpenAI or Cohere
   - §3: Mixed API prefix scheme — Phase 1 routes unprefixed, Phase 2+ under `/api`
   - §5: Six existing Celery queues: default, ner, intelligence, claims, nli, credibility
   - §7: Features NOT yet implemented — these are the Phase 3 starting point
   - §13: Actual env vars in `.env`

2. **`NexusMind_Phase3_Plan.md`** (same folder as this file). The full plan. Read
   Sections 0 (constraints), 1 (tracks), 11 (migration order), 12 (routes), 19
   (explicitly out of scope).

### Step 2 — Orient yourself in the repo

Run these PowerShell commands to get oriented (this is a native Windows project —
no bash, no Docker):

```powershell
Get-ChildItem -Recurse -Filter "*.py" | Select-Object -First 60 -ExpandProperty FullName
Get-ChildItem -Recurse -Filter "*.tsx" | Select-Object -First 60 -ExpandProperty FullName
```

Then read:
- `backend/app/core/config.py` — all env vars the app reads
- `backend/app/workers/celery_app.py` — registered queues
- `backend/alembic/versions/` — list all migration files, identify the current head
- `backend/app/services/ocr.py` — this already exists; read it before Phase 3.3
- `backend/app/services/retrieval.py` — current vector-only search; Phase 3.1
  rewrites this

### Step 3 — Report back before writing any code

Tell me:
1. The current Alembic head (latest applied migration filename)
2. The Celery queues registered in `celery_app.py`
3. Whether `services/ocr.py` exists and what it currently does
4. Anything that contradicts what `NexusMind_Phase2_5_Changes.md` claims is built

Wait for acknowledgement before starting Phase 3.1.

---

## PART 1 — NON-NEGOTIABLE CONSTRAINTS

These apply to every line of code in Phase 3. Do not deviate without flagging.

- **No Docker.** Native Windows binaries only. PowerShell scripts to start
  services. Anything that requires Linux containers is out.
- **No cloud object storage.** All files go through the existing `StorageService`
  writing to `DATA_DIR` on local disk.
- **Zero paid services.** Only keys permitted: `GROQ_API_KEY` (free tier),
  `GEMINI_API_KEY` (free tier), a personal Notion integration token the user
  provides. No OpenAI, no Cohere, no Sentry, no Anthropic, no ElevenLabs, no AWS.
- **768-dim vectors on the chunk path.** The pgvector HNSW index is `vector(768)`.
  Never introduce a different dimension on `chunks.embedding`.
- **Mixed API prefix scheme.** Phase 3 routes go under `/api` (Phase 2 convention),
  except routes that extend Phase 1 unprefixed routes (match their existing prefix).
- **Single-user-per-account.** Do not add `workspace_id`.
- **Every new feature gets at least one test** and a README section under
  `docs/phase3/`.

---

## PART 2 — WORKING AGREEMENT

- Before writing code for each sub-phase, write a short plan (5–10 bullets) of
  what files you will create or change. Wait for approval before coding.
- When you find a contradiction between this prompt and the actual codebase, flag
  it and ask. Do not silently adapt.
- For each Alembic migration, generate the file but **do not run it**. Print the
  exact `alembic upgrade` command for me to run.
- For each new Python dependency, run `pip install <pkg>` and update
  `backend/requirements.txt` with the pinned version. For frontend deps, run
  `npm install <pkg>` in `frontend/` and state the pinned version.
- Run the existing test suite after every meaningful change. If anything that
  passed before now fails, stop and fix it before continuing.
- Do not refactor code outside the scope of the current sub-phase.
- Commit after each sub-phase completes. Tag: `phase-3.X-complete`.

---

## PART 3 — IMPLEMENTATION (7 sub-phases)

Work through sub-phases in order: 3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6.
Sub-phase 3.7 (Grafana) can run in parallel with any of 3.4, 3.5, or 3.6.
Do not start a sub-phase until the previous one passes its definition of done.

---

### SUB-PHASE 3.1 — Hybrid Retrieval + Reranker + Search Page

**Goal:** Replace vector-only search with BM25 + vector + RRF + reranker.
Everything downstream (Q&A, search page, contradiction detection, spaced
repetition cards) depends on retrieval quality. Ship this first.

#### Deliverables

**1. Alembic migration `0008_chunk_tsvector`**
- Add `tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(text, ''))) STORED` column on `chunks`
  (or use an explicit column + trigger if your Postgres version doesn't support generated tsvectors)
- Create GIN index: `CREATE INDEX chunks_tsv_gin ON chunks USING GIN(tsv)`
- Add trigger for non-generated approach:
  ```sql
  CREATE TRIGGER chunks_tsv_update BEFORE INSERT OR UPDATE ON chunks
  FOR EACH ROW EXECUTE FUNCTION tsvector_update_trigger(tsv, 'pg_catalog.english', text);
  ```
- Include a backfill statement: `UPDATE chunks SET tsv = to_tsvector('english', coalesce(text, ''))`
- Provide the exact `alembic upgrade head` command

**2. `backend/app/services/retrieval.py` — full rewrite of the retrieval path**

Add these functions (keep existing `retrieve()` signature working as a shim
during migration, then swap it to call `hybrid_search`):

```python
async def bm25_search(query: str, user_id: UUID,
                      top_k: int = 50,
                      filters: dict | None = None) -> list[tuple[UUID, float]]:
    """Returns (chunk_id, bm25_score) list ordered by ts_rank_cd."""

def rrf_merge(rank_lists: list[list[UUID]], k: int = 60) -> list[UUID]:
    """Pure function. Merges multiple ranked lists via Reciprocal Rank Fusion."""
    scores: dict[UUID, float] = {}
    for ranks in rank_lists:
        for pos, chunk_id in enumerate(ranks):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + pos + 1)
    return [cid for cid, _ in sorted(scores.items(), key=lambda x: -x[1])]

def rerank(query: str, chunks: list[Chunk], top_k: int = 10) -> list[Chunk]:
    """CrossEncoder rerank. Lazy-loads model on first call."""

async def hybrid_search(query: str, user_id: UUID,
                        top_k: int = 10,
                        filters: dict | None = None) -> list[Chunk]:
    """Full pipeline: vector top-50 + BM25 top-50 → RRF top-30 → rerank top-10."""
```

Filter shape (applied at SQL level in both vector and BM25 stages, before fusion):
```python
filters = {
    "source_type": str | None,          # e.g. "pdf", "web", "audio"
    "date_from": datetime | None,
    "date_to": datetime | None,
    "topic_tag": str | None,            # matches against document_intelligence JSONB
    "min_credibility": float | None,    # 0.0–1.0
    "entity_id": UUID | None,           # join via entities → chunks
}
```

**3. Reranker — `BAAI/bge-reranker-base`**
- `pip install sentence-transformers` if not already in requirements
- Lazy-load via a module-level singleton: `_reranker: CrossEncoder | None = None`
- Add `RERANKER_ENABLED=true` to `config.py` and `.env.example`
- When `RERANKER_ENABLED=false`, return RRF top-k directly (no CrossEncoder call)
- The model is ~500MB RAM on CPU; 300–600ms for 30 pairs

**4. Update `/qa` endpoint**
- Add `filters` field to the `QaRequest` Pydantic schema (all fields optional)
- Route through `hybrid_search` instead of the old vector-only path
- Existing `/qa` tests must still pass

**5. New endpoint `POST /api/search`**
- Body: `{ "query": str, "filters": {...}, "top_k": int = 10 }`
- Returns: ranked chunks with `chunk_text`, `document_title`, `page_number`,
  `similarity_score`, `credibility_score`, `source_type`, `topic_tags`
- Redis caching:
  - Key: `search:` + SHA-256(`query || sorted(filters) || top_k`)
  - TTL: 5 minutes
  - On ingestion completion, evict stale cache:
    ```python
    for key in redis_client.scan_iter("search:*"):
        redis_client.delete(key)
    ```
  - Use `scan_iter`, not `keys()` — safer on large keyspaces

**6. New Next.js page `/search`**
- `npm install mark.js @types/mark.js` — for snippet highlighting
- Components:
  - `components/search/SearchBar.tsx` — 300ms debounced input
  - `components/search/FilterPanel.tsx` — source type chips, date-range picker,
    topic multi-select, credibility slider (0–1, step 0.1)
  - `components/search/ResultCard.tsx` — title, highlighted snippet, page,
    reuses `CredibilityBadge.tsx`
- URL-state filters via `useSearchParams` so searches are shareable
- Click result → navigate to `/library/[id]` with `?chunk=<chunk_id>` anchor
- Add `useSearch.ts` hook and `services/search.ts` client
- Add **Search** link to `app/(app)/layout.tsx` nav

**7. Tests**
- `tests/test_bm25.py` — BM25 query path, tsvector trigger fires on insert
- `tests/test_rrf.py` — pure function tests with fixture rank lists (including
  ties, overlapping IDs, empty lists)
- `tests/test_reranker.py` — mock CrossEncoder, assert result order changes
  for a deliberately mis-ranked input
- `tests/test_search_api.py` — integration test for `POST /api/search` with
  filter combinations (source_type, min_credibility)
- `tests/retrieval_eval.py` — `pip install ranx`; create a JSON fixture of
  20–30 hand-labelled query→chunk relevance pairs; compute NDCG@10 and MRR@10;
  print results to stdout; record baseline in `docs/phase3/retrieval_baseline.md`

**Definition of done**
- All new tests pass; `test_qa.py` still passes
- `POST /api/search` returns filtered results in < 800ms p95 on cached queries
- NDCG@10 baseline is printed and saved
- `/search` page renders, filters work, mark.js highlights query terms

---

### SUB-PHASE 3.2 — SSE Streaming + Conversation History

**Goal:** Stream Q&A tokens to the UI; surface the conversation history that has
been persisting in the DB since Phase 1.

#### Important: auth constraint on streaming

Native browser `EventSource` cannot send custom headers, including
`Authorization: Bearer <token>`. This project uses JWT in the Authorization
header for all authenticated routes. Therefore:

- **Do NOT use `EventSource` or `GET` for the streaming endpoint.**
- Use `POST /qa/stream` returning FastAPI `StreamingResponse`.
- The frontend reads the stream with `fetch()` + `response.body.getReader()`.
- This is more secure (token stays in the header, not the URL) and identical
  from the FastAPI side.

#### Deliverables

**1. `backend/app/services/llm.py` — add streaming wrapper**

Add an async generator method alongside the existing non-streaming call:

```python
async def stream(self, prompt: str) -> AsyncGenerator[str, None]:
    """Yields token strings as they arrive from the Groq streaming API."""
    response = await self.client.chat.completions.create(
        model=self.model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        temperature=self.temperature,
    )
    prompt_tokens = 0
    completion_tokens = 0
    async for chunk in response:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta
        if chunk.usage:  # Groq sends usage in the final chunk
            prompt_tokens = chunk.usage.prompt_tokens
            completion_tokens = chunk.usage.completion_tokens
    # Increment Prometheus counters (reuse the existing metric from core/metrics.py)
    LLM_TOKENS_TOTAL.labels(provider="groq", model=self.model,
                             direction="prompt").inc(prompt_tokens)
    LLM_TOKENS_TOTAL.labels(provider="groq", model=self.model,
                             direction="completion").inc(completion_tokens)
```

**2. New endpoint `POST /qa/stream`**

```python
@router.post("/qa/stream")
async def qa_stream(request: QaStreamRequest,
                    current_user: User = Depends(get_current_user)):
    async def generate():
        retrieved = await hybrid_search(request.query, current_user.id,
                                        filters=request.filters)
        if not retrieved or max_similarity(retrieved) < QA_NO_SOURCE_THRESHOLD:
            yield f"event: no_source\ndata: {{}}\n\n"
            return
        async for token in llm.stream(build_prompt(retrieved, request.query,
                                                    conversation_history)):
            yield f"event: token\ndata: {json.dumps({'t': token})}\n\n"
        citations = resolve_citations(full_answer, retrieved)
        yield f"event: citations\ndata: {json.dumps(citations)}\n\n"
        yield "event: done\ndata: {}\n\n"
        await persist_messages(...)  # append to messages table after stream
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )
```

Note: this is `POST /qa/stream` — no `/api` prefix, consistent with Phase 1's
`POST /qa`.

**3. Sliding-window conversation memory**

When assembling the LLM prompt for `/qa` or `/qa/stream`:
- Load the last 6 messages from the conversation (3 user + 3 assistant turns max)
- Prepend them to the retrieved-chunks prompt
- This applies to both the streaming and non-streaming paths

**4. Auto-title via Ollama**

After the first assistant response in a new conversation:
- Fire a Celery task on the existing `intelligence` queue (no new queue needed)
- Task calls Ollama `qwen2.5:7b-instruct` with the first user message,
  asks for a 4–6 word title in JSON mode
- Updates `conversations.title` in the DB
- Do not block the user-visible stream on this

**5. New conversation endpoints** (all prefixed `/api/`)

- `GET /api/conversations` — paginated list, newest first, returns
  `[{id, title, created_at, message_count}]`
- `GET /api/conversations/{id}` — full message thread
- `PATCH /api/conversations/{id}` — body `{ "title": str }` — rename
- `DELETE /api/conversations/{id}` — hard delete cascade

**6. Frontend `/qa` page updates**

- Collapsible left sidebar listing conversations (new `ConversationSidebar.tsx`)
- **New conversation** button at the top of the sidebar
- Click conversation → load messages and continue the thread
- Inline rename: double-click conversation title → editable input
- **Streaming message component** (`StreamingMessage.tsx`):
  ```typescript
  const response = await fetch('/qa/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}` },
    body: JSON.stringify({ query, conversation_id, filters }),
  });
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    // Parse SSE events from the decoded text chunk
    parseSSEChunk(decoder.decode(value));
  }
  ```
- Citation chips appear after the `citations` event fires (not during streaming)
- Add `useStreamingQa.ts` hook and `useConversations.ts` hook

**7. Tests**
- `tests/test_qa_stream.py` — integration test; connect to `POST /qa/stream`,
  collect events, assert sequence: one or more `token` events → `citations` → `done`
- `tests/test_conversations.py` — CRUD: create, list, rename, delete
- `tests/test_sliding_window.py` — assert 7+ messages get truncated to 6 when
  building the LLM prompt; verify the prompt string contains exactly the last 6

**Definition of done**
- First token visible in UI within 600ms of submit (1.5s on cold retrieval)
- Conversations persist across page reloads; rename and delete work
- Existing `test_qa.py` still passes (non-streaming path unchanged)

---

### SUB-PHASE 3.3 — Multi-Source Ingestion

**Goal:** Accept web URLs, scanned PDFs (OCR), audio files, YouTube transcripts,
Notion pages, and ZIP archives — all through the existing StorageService + Celery
pipeline.

#### Before you start

Read `backend/app/services/ocr.py` — it **already exists**. Phase 3.3 wires it
into the parse worker decision tree; do not recreate it.

#### Deliverables

**1. Migrations** (3 new, numbered to follow 0008 in sequence)

`0009_url_documents` — extend `documents`:
```sql
ALTER TABLE documents
  ADD COLUMN source_url      TEXT,
  ADD COLUMN captured_at     TIMESTAMPTZ,
  ADD COLUMN extension_capture BOOLEAN DEFAULT FALSE,
  ADD COLUMN media_type      TEXT DEFAULT 'text';  -- text|web|audio|video|notion
```

`0010_notion_state`:
```sql
CREATE TABLE notion_integrations (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_encrypted  TEXT NOT NULL,
    workspace_name   TEXT,
    created_at       TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE notion_pages (
    page_id               TEXT PRIMARY KEY,
    integration_id        UUID NOT NULL REFERENCES notion_integrations(id) ON DELETE CASCADE,
    document_id           UUID REFERENCES documents(id) ON DELETE SET NULL,
    notion_last_edited_at TIMESTAMPTZ,
    last_synced_at        TIMESTAMPTZ
);
```

`0011_audio_segments`:
```sql
CREATE TABLE audio_segments (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id      UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    start_seconds FLOAT NOT NULL,
    end_seconds   FLOAT NOT NULL
);
CREATE INDEX audio_segments_chunk ON audio_segments(chunk_id);
```

Provide exact `alembic upgrade head` command after generating each file.

**2. Web URL ingestion**

```powershell
pip install trafilatura httpx
```

New endpoint `POST /ingest/url` body `{ "url": str }`:
- Validate URL scheme (https/http only)
- Celery task on `default` queue:
  ```python
  async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
      resp = await c.get(url, headers={"User-Agent": "NexusMind/1.0"})
  text = trafilatura.extract(resp.text, include_links=True,
                              include_tables=True, output_format='txt')
  meta = trafilatura.extract_metadata(resp.text)
  ```
- Dedupe via `SHA-256(canonical_url)` stored in `content_hash`
- Reject if `len(text) < 200` with a user-facing error
- Write the cleaned text as a `.txt` file to `DATA_DIR/{user_id}/{doc_id}/content.txt`
  (uniform storage contract)
- Set `media_type='web'`, `source_url=url`, `captured_at=now()`
- Route into standard `parse → chunk → embed → ner → ...` chain

**3. OCR pipeline wiring**

`pip install pytesseract pillow`

At API startup, check Tesseract is installed:
```python
import shutil
if not shutil.which("tesseract"):
    logger.warning("Tesseract not found — scanned PDFs will be skipped",
                   hint="winget install UB-Mannheim.TesseractOCR")
```

In the parse worker, after pypdf text extraction:
```python
avg_chars_per_page = total_chars / max(page_count, 1)
if avg_chars_per_page < 100:
    # Route to OCR queue — uses existing services/ocr.py
    run_ocr.apply_async(args=[document_id], queue="ocr")
    return  # parse worker yields; ocr worker continues the chain
```

New Celery queue `ocr`. The OCR worker:
- Calls the existing `ocr.py` service
- Replaces the parsed text in `DATA_DIR/{user_id}/{doc_id}/parsed.json`
- Adds `ocr_quality` field: `"high"` if avg word length 4–8 chars and dict-word
  ratio > 0.7, `"medium"` if ratio > 0.4, `"low"` otherwise
- Continues the chain: `chunk → embed → ...`

Update `scripts/start-worker.ps1` to include the `ocr` queue.

**4. Audio transcription**

```powershell
pip install faster-whisper
```

Verify ffmpeg at startup:
```python
if not shutil.which("ffmpeg"):
    logger.warning("ffmpeg not found — audio/video ingest unavailable",
                   hint="winget install ffmpeg")
```

New env var `AUDIO_MAX_UPLOAD_BYTES=524288000` (500MB) — add to `config.py`
and `.env.example`. Do NOT change the global `MAX_UPLOAD_BYTES`.

New endpoint `POST /ingest/audio` — multipart, enforces `AUDIO_MAX_UPLOAD_BYTES`.

Extend `ALLOWED_MIME_TYPES` (or add a separate `AUDIO_MIME_TYPES`):
`audio/mpeg, audio/wav, audio/x-m4a, audio/ogg, video/mp4`

New Celery queue `transcription`. Worker:
```python
from faster_whisper import WhisperModel
_whisper: WhisperModel | None = None

def get_whisper():
    global _whisper
    if _whisper is None:  # lazy-load on first task
        _whisper = WhisperModel("base.en", device="cpu", compute_type="int8")
    return _whisper

def transcribe_audio(audio_path: str) -> list[dict]:
    segments, _ = get_whisper().transcribe(audio_path, beam_size=5, vad_filter=True)
    return [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
```

For `video/mp4`: extract audio first:
```python
subprocess.run(["ffmpeg", "-i", input_path, "-vn", "-acodec", "libmp3lame",
                 output_audio_path], check=True)
```

After transcription:
- Stitch segments into a single text string
- Store timestamps in `audio_segments` linked to the chunks they fall within
- Citations for audio documents display `at {mm:ss}` from `audio_segments`

Update `scripts/start-worker.ps1` to include `transcription` queue.

**5. YouTube transcripts**

```powershell
pip install youtube-transcript-api yt-dlp
```

New endpoint `POST /ingest/youtube` body `{ "url": str }`.

Worker logic:
```python
from youtube_transcript_api import YouTubeTranscriptApi
video_id = extract_video_id(url)  # parse from URL
try:
    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
except:
    # Fall back: yt-dlp audio extraction → faster-whisper
    audio_path = yt_dlp_extract_audio(url)
    transcript = transcribe_audio(audio_path)

# Metadata via yt-dlp
info = yt_dlp_get_info(url)  # title, channel, upload_date, duration
```

Route into standard pipeline. Store timestamps in `audio_segments`.
Dedupe via SHA-256 of the canonical YouTube URL.

**6. Notion connector**

```powershell
pip install notion-client cryptography
```

Do **not** install `notion-to-md` — there is no stable Python equivalent.
Instead, write a `blocks_to_markdown(blocks: list[dict]) -> str` helper in
`backend/app/services/notion_parser.py` that handles:
`paragraph`, `heading_1`, `heading_2`, `heading_3`, `bulleted_list_item`,
`numbered_list_item`, `code`, `quote`, `divider`. Skip unsupported block types
with a `# [unsupported block: {type}]` comment.

New endpoints (no `/api` prefix — `notion` is a new top-level resource):
- `POST /notion/connect` body `{ "token": str, "workspace_name": str }`
  - Encrypt token at rest with Fernet using `JWT_SECRET` as the key material
  - Store in `notion_integrations`
- `POST /notion/sync` — trigger sync now, return `{ "job_id": str }`
- `POST /notion/schedule` body `{ "hours": int }` — set Celery beat schedule
- `DELETE /notion/connect/{id}` — revoke integration

Sync worker (on `intelligence` queue — Notion sync is low-frequency):
- Iterate databases the integration can see via `notion-client`
- For each page, convert blocks via `blocks_to_markdown()`
- Sleep 350ms between API calls to respect Notion rate limits
- Idempotency: skip pages where `notion_last_edited_time <= last_synced_at`
- Route cleaned markdown into standard parse → chunk → embed chain
- Set `media_type='notion'`, `source_url=notion_page_url`

**7. Bulk ZIP import**

New endpoint `POST /ingest/zip` — multipart upload, same size limit as
`MAX_UPLOAD_BYTES`.

Worker:
```python
with zipfile.ZipFile(zip_path) as zf:
    for entry in zf.infolist():
        # Security: reject path traversal
        if ".." in entry.filename or entry.filename.startswith("/"):
            warnings.append(f"Skipped (path traversal): {entry.filename}")
            continue
        # Check MIME
        mime = mimetypes.guess_type(entry.filename)[0]
        if mime not in ALLOWED_MIME_TYPES:
            warnings.append(f"Skipped (unsupported type): {entry.filename}")
            continue
        # Extract and enqueue
        data = zf.read(entry.filename)
        enqueue_ingest(data, entry.filename, mime, user_id)
```

Response includes `{ "queued": [...], "skipped": [...] }`.

**8. Frontend `/upload` page additions**

Add three new tabs alongside the existing File Upload tab: **URL**, **Audio/Video**,
**YouTube**.

New page `/connections`:
- Notion: token paste field, workspace name, sync-now button, schedule input,
  sync status
- ZIP import: drag-drop zone

New components:
- `ingest/UrlImport.tsx`
- `ingest/AudioUpload.tsx`
- `ingest/YouTubeImport.tsx`
- `ingest/NotionConnect.tsx`
- `ingest/ZipImport.tsx`

Add **Connections** link to `app/(app)/layout.tsx` nav.

**9. Tests**
- `tests/test_ingest_url.py` — mock httpx + trafilatura; assert document created,
  dedup works, short content rejected
- `tests/test_ingest_audio.py` — use a 3-second fixture WAV; mock faster-whisper;
  assert `audio_segments` rows created
- `tests/test_ingest_youtube.py` — mock `YouTubeTranscriptApi`; assert transcript
  stitched and segments stored
- `tests/test_ingest_notion.py` — mock notion-client; assert `blocks_to_markdown`
  output, idempotency (page not re-ingested if `last_edited <= last_synced`)
- `tests/test_ingest_zip.py` — fixture zip with valid + path-traversal + wrong-mime
  entries; assert correct skips and warnings
- `tests/test_ocr.py` — feed a known scanned-PDF fixture (or mock pypdf to return
  0 chars/page); assert OCR task is enqueued, `ocr_quality` field set

**Definition of done**
- All five source types (URL, audio, YouTube, Notion, ZIP) ingest representative
  samples end-to-end
- Dedupe works per source type
- Audio and YouTube citations show `at mm:ss` in `/qa` responses
- Tesseract unavailability logs a warning and marks the document, not a crash
- ffmpeg unavailability logs a warning and rejects audio/video with clear error
- All new tests pass; existing tests pass

---

### SUB-PHASE 3.4 — Browser Extension

**Goal:** Chrome/Firefox extension for one-click page save, highlight capture,
and quick search popup. Lives in `extension/` at the repo root.

#### Deliverables

**1. Scaffold — `extension/` directory**

```powershell
cd extension
npm init -y
npm install -D vite vite-plugin-web-extension typescript @types/chrome
npm install react react-dom @mozilla/readability webextension-polyfill tailwindcss
```

`manifest.json` (Manifest V3):
```json
{
  "manifest_version": 3,
  "name": "NexusMind Clipper",
  "version": "0.1.0",
  "permissions": ["activeTab", "contextMenus", "storage", "scripting", "notifications"],
  "host_permissions": ["<all_urls>"],
  "background": { "service_worker": "src/background/main.ts" },
  "action": { "default_popup": "src/popup/index.html" },
  "content_scripts": [{ "matches": ["<all_urls>"],
                         "js": ["src/content/main.ts"],
                         "run_at": "document_idle" }],
  "options_ui": { "page": "src/options/index.html", "open_in_tab": true }
}
```

**2. Content script `src/content/main.ts`**

```typescript
import { Readability } from '@mozilla/readability';
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.action !== 'extract') return;
  const clone = document.cloneNode(true) as Document;
  const article = new Readability(clone).parse();
  sendResponse({ article, url: window.location.href });
});
```

**3. Background service worker `src/background/main.ts`**

- On toolbar click: inject content script → receive article → POST to
  `/ingest/url-content` with stored JWT
- On context menu click (selected text): POST selection + surrounding 200 chars
  to `POST /api/notes/highlight` (this endpoint is stubbed here; fully wired
  in Phase 3.5 annotations)
- Show `chrome.notifications` on success or failure

**4. Popup `src/popup/Popup.tsx`**

- Status line: logged in as `<email>` or "Not connected"
- Search box → `POST /api/search` → show top 5 results inline
- Recent saves: `GET /documents?limit=10` → show as a list
- Settings link → opens options page

**5. Options page `src/options/Options.tsx`**

- Base URL field (default `http://localhost:8000`)
- Token paste field (the extension-scoped JWT from the web app)
- "Test connection" → `GET /auth/me` with the stored token
- Revoke / clear local data

**6. Backend — extension-scoped JWT**

Extend `backend/app/auth/jwt.py`:
```python
def create_token(user_id: UUID, email: str,
                 expiry_seconds: int = JWT_EXPIRY_SECONDS,
                 scope: list[str] | None = None) -> str:
    payload = {"sub": str(user_id), "email": email,
               "exp": ..., "iat": ...,
               "scope": scope or []}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def require_scope(required: str):
    """FastAPI dependency — raises 403 if token scope doesn't include `required`."""
    def dep(token_data = Depends(get_current_user_token)):
        if required not in (token_data.scope or []):
            raise HTTPException(status_code=403, detail="Insufficient scope")
    return dep
```

Apply `require_scope("ingest")` on `/ingest/*` endpoints when called via extension
token. Full-session JWTs (scope=[]) bypass the check.

New backend endpoints:
- `POST /ingest/url-content` — body `{ url, title, content, byline, captured_at }`.
  Accepts pre-extracted text from the extension (skip trafilatura fetch step).
  Sets `extension_capture=True` on the document. Routes into standard pipeline.
- `POST /api/notes/highlight` — body `{ url, highlighted_text, context, title }`.
  In Phase 3.4: create a stub Document if the URL is new, store the highlighted
  text as the document body. Add a TODO comment to wire into the annotation system
  when Phase 3.5 lands.
- `GET /api/extension/token` (web app authenticated) — issues a JWT with
  `scope=["ingest", "search"]` and `expiry=90 days`. One token per user;
  issuing a new one invalidates the old by updating a `token_version` field on
  the user (add this column if not present).

**7. Web app `/connections` page additions**

- Extension token section: masked display, click to reveal, "Regenerate" button
- Install instructions section linking to Chrome / Firefox dev mode load process

**8. Build**

```powershell
cd extension && npm run build  # produces extension/dist/
```

Document loading in `docs/phase3/extension_install.md`:
- Chrome: `chrome://extensions` → developer mode → Load unpacked → select `dist/`
- Firefox: `about:debugging` → Load Temporary Add-on → select `dist/manifest.json`

**9. Tests**
- `tests/test_ingest_url_content.py` — backend test for `/ingest/url-content`
- `tests/test_extension_token.py` — issue token, verify scope, test revocation
- Manual smoke test steps documented in `docs/phase3/extension_install.md`

**Definition of done**
- Extension loads unpacked in Chrome and Firefox
- Toolbar button saves current article; appears in `/library` within 15 seconds
- Popup search returns results from the user's library
- Token revocation from web app disconnects extension on next request

---

### SUB-PHASE 3.5 — Notes & Annotation System

**Goal:** Inline document highlights with notes, graph-integrated user insights,
annotation search.

#### Deliverables

**1. Migration `0012_annotations`**

```sql
CREATE TABLE annotations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

**2. Annotation endpoints** (all under `/api/`)

- `POST /api/annotations`
- `GET /api/annotations` with `?document_id`, `?tag`, `?from`, `?to`, pagination
- `PATCH /api/annotations/{id}` — edit note, tags, color
- `DELETE /api/annotations/{id}`
- `GET /api/annotations/export?format=md|csv`

**3. Graph integration — `user_insight` entity type**

On annotation create where `note` is non-empty, fire a Celery task on the
existing `ner` queue:
```python
def create_user_insight(annotation_id: UUID):
    # Load annotation
    # Create entity with type='user_insight', name=note[:200]
    # Embed via existing entity_embedding service (all-MiniLM-L6-v2)
    # For each entity already linked to the source chunk:
    #   Create entity_edge: user_insight → entity, type='relates_to', confidence=1.0
```

In the Graph Explorer (`components/graph/GraphCanvas.tsx`), render `user_insight`
nodes in amber with a small pencil icon. The entity type is new but the graph
schema already supports arbitrary types.

**4. Retrieval integration**

Index each annotation as a chunk in the vector store:
```python
# On annotation create (after DB insert):
chunk = Chunk(
    document_id=annotation.document_id,
    user_id=annotation.user_id,
    text=f"{annotation.highlight_text}\n\n{annotation.note or ''}".strip(),
    source_type='user_annotation',
    ...
)
# embed via existing embedding service, insert into chunks with HNSW update
```

The `source_type='user_annotation'` filter chip from Phase 3.1 then works
automatically — annotations appear in `/qa` and `/api/search` results.

**5. Wire `POST /api/notes/highlight` from Phase 3.4**

Replace the TODO stub with the real annotation pipeline:
```python
# Find or create stub document for this URL
# Create annotation: highlight_text=highlighted_text, note=context
# Trigger user_insight task if note is non-empty
```

**6. Frontend**

`components/annotations/HighlightOverlay.tsx` mounted on `/library/[id]`:
- Use `window.getSelection()` and `Range.getBoundingClientRect()` for positioning
- No heavy editor library — a floating `div` positioned with `getBoundingClientRect()`
- Popover: color picker (5 colors), note `<textarea>`, tag `<input>`, Save/Cancel
- On Save: `POST /api/annotations` with `char_start/char_end` from
  `Selection.getRangeAt(0).startOffset` and `endOffset`

On document viewer load, fetch annotations for the document:
- Apply `<mark>` spans at `char_start`/`char_end` ranges in the rendered text
- Color each mark with the annotation's color via Tailwind `bg-yellow-200` etc.
- Hover → tooltip with note preview
- Click → side panel (reuse `EntitySidePanel.tsx` pattern)

New page `/notes`:
- `components/annotations/AnnotationCard.tsx` — compact card view
- Filter sidebar: tag multi-select, document filter, date range
- Click → navigate to `/library/[id]?annotation=<id>` which scrolls and highlights

`GET /api/annotations/export`:
- `?format=md` → one markdown block per annotation with source and note
- `?format=csv` → CSV with columns: document, page, highlight, note, tags, created

Add **Notes** link to nav.

**7. Tests**
- `tests/test_annotations_crud.py` — create, list (with filters), update, delete
- `tests/test_annotations_graph.py` — assert `user_insight` entity and edges
  created on non-empty note
- `tests/test_annotations_retrieval.py` — assert annotation text surfaces in
  `/api/search` when `source_type` filter includes `user_annotation`
- `tests/test_annotations_export.py` — verify markdown and CSV format for a
  seeded set of annotations

**Definition of done**
- Highlights persist across page reloads; render at correct character positions
- Non-empty notes create `user_insight` entities visible in Graph Explorer
- Annotations surface in `/qa` retrieval
- Markdown and CSV exports are valid and non-empty
- `POST /api/notes/highlight` from the extension creates a real annotation

---

### SUB-PHASE 3.6 — Spaced Repetition Flashcards

**Goal:** Auto-generate flashcards from document chunks via Ollama; schedule
reviews with SM-2.

#### Deliverables

**1. Migration `0013_flashcards`**

```sql
CREATE TABLE flashcards (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id      UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
    rating       SMALLINT NOT NULL,  -- 0=Again 1=Hard 2=Good 3=Easy
    reviewed_at  TIMESTAMPTZ DEFAULT now()
);
```

**2. SM-2 implementation — `backend/app/services/srs.py`**

```python
from dataclasses import dataclass
from datetime import date

@dataclass
class CardState:
    reps: int
    interval: int
    ease: float
    due: date

def sm2(state: CardState, rating: int) -> CardState:
    """rating: 0=Again, 1=Hard, 2=Good, 3=Easy."""
    q = rating + 2  # map 0..3 to SM-2's 2..5
    if q < 3:
        return CardState(reps=0, interval=1, ease=state.ease,
                         due=date.today() + timedelta(days=1))
    if state.reps == 0:
        interval = 1
    elif state.reps == 1:
        interval = 6
    else:
        interval = round(state.interval * state.ease)
    ease = max(1.3, state.ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    return CardState(reps=state.reps + 1, interval=interval, ease=ease,
                     due=date.today() + timedelta(days=interval))
```

**3. Card generation worker**

New Celery queue `cards`. New task `generate_cards(document_id)`:

```python
CARD_PROMPT = """You will receive a document chunk. Generate up to 3 flashcards.
Each card must have a clear question and a short, specific answer drawn directly
from the chunk. Return JSON only:
{"cards": [{"q": "...", "a": "..."}]}
If the chunk is not factual content, return {"cards": []}."""

def generate_cards(document_id: UUID):
    chunks = load_chunks(document_id)
    for chunk in chunks:
        if already_has_cards(chunk.id):
            continue  # idempotent
        result = ollama_json(CARD_PROMPT, chunk.text)
        for card in result.get("cards", []):
            insert_flashcard(user_id, chunk.id, document_id,
                             card["q"], card["a"])
```

**This is opt-in.** Do not trigger automatically after intelligence completes.
Trigger only when:
- User clicks "Generate cards" on a document in `/library/[id]`
- OR global setting `AUTO_GENERATE_CARDS=true` is set in `.env`

**4. Endpoints** (all `/api/cards/...`)

- `POST /api/cards/generate` body `{ "document_id": UUID }` — kick off task,
  return `{ "job_id": str }`
- `GET /api/cards/due` — cards where `due_date <= today()` and `NOT suspended`,
  ordered by `due_date ASC`
- `POST /api/cards/{id}/review` body `{ "rating": 0|1|2|3 }` — apply SM-2,
  insert `flashcard_reviews` row, return updated `{ due_date, interval_days, ease }`
- `GET /api/cards` — list with `?document_id`, `?suspended`, pagination
- `PATCH /api/cards/{id}` — edit question, answer, or `suspended`
- `DELETE /api/cards/{id}`
- `GET /api/cards/stats`:
  ```json
  {
    "cards_total": 120,
    "cards_due_today": 14,
    "cards_mastered": 47,
    "current_streak": 5,
    "reviews_last_7_days": 63
  }
  ```
  `cards_mastered` = reps >= 3; `current_streak` = consecutive calendar days
  with at least one review in `flashcard_reviews`

**5. Worker script update**

Update `scripts/start-worker.ps1` — final complete queue list:
```
default,ner,intelligence,claims,nli,credibility,ocr,transcription,cards
```

**6. Frontend**

New page `/flashcards`:
- Hero: due-today count + "Start review" button
- Stats row: streak, mastery %, total cards
- Activity chart (reviews per day, last 30 days):
  - Use D3.js (already in the project from `GraphCanvas.tsx`) for a simple
    bar chart — do NOT add Recharts unless it is already in `package.json`
  - If D3 feels heavy for a bar chart, use plain Tailwind `flex`+`h-*` bars

`components/cards/ReviewModal.tsx`:
- Card front: question text
- Space / click to flip
- Card back: answer text + link to source chunk in `/library/[id]`
- Four rating buttons: Again / Hard / Good / Easy
- Keyboard shortcuts: `1`=Again, `2`=Hard, `3`=Good, `4`=Easy
- CSS 3D flip animation (`transform-style: preserve-3d`, `rotateY(180deg)`) —
  no animation library
- Auto-advance to next card after rating (300ms delay so user sees the button)

Per-document panel on `/library/[id]`:
- "Generate cards" button — idempotent (skips chunks that already have cards)
- List of existing cards for this document with edit/delete/suspend

Browser notifications (web app only, not extension):
```typescript
// In app/(app)/layout.tsx
useEffect(() => {
  if (!('Notification' in window)) return;
  const check = async () => {
    const stats = await fetchCardStats();
    if (stats.cards_due_today > 0 && Notification.permission === 'granted') {
      new Notification('NexusMind', {
        body: `${stats.cards_due_today} cards due for review`,
      });
    }
  };
  Notification.requestPermission();
  check();
  const timer = setInterval(check, 60 * 60 * 1000); // every hour
  return () => clearInterval(timer);
}, []);
```

Add **Flashcards** link to `app/(app)/layout.tsx` nav.

**7. Tests**
- `tests/test_sm2.py` — all four ratings; reps=0, reps=1, reps>1 transitions;
  ease floor at 1.3; due_date advances correctly
- `tests/test_cards_generation.py` — mock Ollama JSON response; assert cards
  land in DB; assert idempotency (second call for same chunk skips)
- `tests/test_cards_review.py` — submit each rating, assert next `due_date` and
  updated `ease` match SM-2 formula
- `tests/test_cards_stats.py` — seed known data; assert all stat fields
  (`streak`, `mastered`, `due_today`)

**Definition of done**
- Card generation creates valid cards for a test document
- All four SM-2 ratings transition state correctly (verified by unit test)
- Review modal works end-to-end with keyboard shortcuts 1–4
- Browser notification fires when due cards exist (manually verified with
  permission granted)
- Stats endpoint returns correct values for seeded data

---

### SUB-PHASE 3.7 — Grafana Dashboards *(runs in parallel with 3.4+)*

**Goal:** Wire the Prometheus metrics already exported at `/metrics` into a
local Grafana OSS instance with four provisioned dashboards.

#### Deliverables

**1. Confirm Prometheus is running**

Read `backend/app/api/metrics.py` and `backend/app/core/metrics.py`. List every
existing metric name and label.

Check if Prometheus is installed: `(Get-Command prometheus -ErrorAction SilentlyContinue)`.

If not installed, write `scripts/install-prometheus.ps1`:
- Download the Windows binary from `github.com/prometheus/prometheus/releases`
- Write `ops/prometheus/prometheus.yml`:
  ```yaml
  global:
    scrape_interval: 15s
  scrape_configs:
    - job_name: nexusmind
      static_configs:
        - targets: ['localhost:8000']
  ```
- Register as a Windows scheduled task (start at login) or document the manual
  start command in `docs/phase3/observability.md`

**2. Add missing Prometheus metrics** (only if not already present)

In `backend/app/core/metrics.py`:

```python
# Celery
CELERY_QUEUE_DEPTH = Gauge('nexusmind_celery_queue_depth', 'Queue depth', ['queue'])
CELERY_TASK_DURATION = Histogram('nexusmind_celery_task_duration_seconds',
                                  'Task duration', ['task', 'queue'])
CELERY_TASK_FAILURES = Counter('nexusmind_celery_task_failures_total',
                                 'Task failures', ['task', 'queue'])

# Retrieval — per stage
RETRIEVAL_DURATION = Histogram('nexusmind_retrieval_duration_seconds',
                                'Retrieval stage latency',
                                ['stage'],  # vector|bm25|rrf|rerank
                                buckets=[.05, .1, .25, .5, 1, 2, 4])
RETRIEVAL_CACHE_HITS = Counter('nexusmind_retrieval_cache_hits_total', 'Cache hits')
RETRIEVAL_CACHE_MISSES = Counter('nexusmind_retrieval_cache_misses_total', 'Cache misses')

# LLM — add `direction` label to existing token counter if not present
LLM_TOKENS_TOTAL = Counter('nexusmind_llm_tokens_total', 'LLM tokens',
                             ['provider', 'model', 'direction'])  # prompt|completion
LLM_REQUESTS = Counter('nexusmind_llm_requests_total', 'LLM requests',
                         ['provider', 'model'])
LLM_DURATION = Histogram('nexusmind_llm_duration_seconds', 'LLM latency',
                           ['provider', 'model'])

# Ingestion
INGESTION_STATUS = Counter('nexusmind_ingestion_status_total', 'Ingestion events',
                            ['source_type', 'status'])
```

Add a periodic Celery task (on `maintenance` queue or via `celery beat`) that
updates `CELERY_QUEUE_DEPTH` gauges by querying Redis queue lengths.

**3. Install Grafana OSS**

Write `scripts/install-grafana.ps1`:
- Download the Windows binary from `grafana.com/grafana/download` (OSS, not
  Grafana Cloud)
- Run on port **3001** (port 3000 is taken by Next.js dev server)
- Write `ops/grafana/grafana.ini` with `http_port = 3001`
- Document start command in `docs/phase3/observability.md`

**4. Provision dashboards**

Grafana provisioning via JSON files (committed to repo, loaded at startup):

`ops/grafana/provisioning/datasources/prometheus.yaml`:
```yaml
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    url: http://localhost:9090
    isDefault: true
```

`ops/grafana/provisioning/dashboards/dashboards.yaml`:
```yaml
apiVersion: 1
providers:
  - name: NexusMind
    folder: NexusMind
    type: file
    options:
      path: /path/to/ops/grafana/dashboards
```

Four dashboard JSON files:

`ops/grafana/dashboards/ingestion.json`:
- Queue depth per queue (time series, one line per queue)
- Task duration p50/p95/p99 (time series)
- Task failure rate (time series)
- Ingestion events by source_type and status (bar gauge)

`ops/grafana/dashboards/retrieval.json`:
- `/qa` and `/api/search` request rate
- Retrieval latency p50/p95/p99 per stage (vector, bm25, rrf, rerank)
- Search cache hit ratio (single stat)

`ops/grafana/dashboards/ai_usage.json`:
- Groq tokens/hour (track against free tier limits)
- Gemini embedding requests/hour
- Ollama request count and average latency
- LLM error rate

`ops/grafana/dashboards/system.json`:
- CPU and memory (via node_exporter if installed; note if unavailable)
- DATA_DIR disk usage (via a small helper that runs `Get-PSDrive` and exposes
  a gauge, or skip and document)
- Postgres active connections
- Redis memory usage

**5. Documentation — `docs/phase3/observability.md`**
- How to start Prometheus and Grafana
- URLs and default credentials
- How to add a new metric
- How to add a new dashboard panel

**6. Test**

Add to `tests/test_metrics.py`:
```python
def test_new_metrics_exported(client):
    resp = client.get("/metrics")
    assert "nexusmind_celery_queue_depth" in resp.text
    assert "nexusmind_retrieval_duration_seconds" in resp.text
    assert "nexusmind_llm_tokens_total" in resp.text
    assert "nexusmind_ingestion_status_total" in resp.text
```

**Definition of done**
- Grafana is reachable at `http://localhost:3001` with Prometheus pre-configured
- All four dashboards render with live data after an hour of usage
- New metrics appear in `/metrics` output and pass the test above

---

## PART 4 — ACCEPTANCE CRITERIA FOR PHASE 3 AS A WHOLE

Phase 3 is complete when all of the following are true:

- ✅ Hybrid retrieval (BM25 + vector + RRF + bge-reranker) is the default path
  for `/qa` and `/api/search`
- ✅ `/search` page exists with working filters; results cache for 5 minutes
- ✅ Q&A streams tokens via `POST /qa/stream` using fetch ReadableStream;
  first token visible within 600ms on cached retrieval
- ✅ Conversation history persists, is listable/renameable/deleteable
- ✅ All five source types ingest successfully: PDF/TXT/MD (existing), web URL,
  audio file, YouTube URL, Notion page, ZIP archive
- ✅ Scanned PDFs route through Tesseract OCR automatically; non-OCR PDFs
  are unaffected
- ✅ Timestamped citations (`at mm:ss`) appear in `/qa` answers for audio and
  YouTube documents
- ✅ Browser extension installs unpacked in Chrome and Firefox; save-page and
  save-selection flows complete in under 15 seconds
- ✅ Annotations persist and render inline in the document viewer
- ✅ Annotations appear as `user_insight` entities in the Graph Explorer
- ✅ Annotations are retrievable in `/qa` with `source_type=user_annotation` filter
- ✅ Flashcard generation produces valid cards via Ollama for a test document
- ✅ SM-2 scheduling is unit-tested for all four ratings
- ✅ Review modal works end-to-end with keyboard shortcuts 1–4
- ✅ Grafana dashboards exist and render with live data
- ✅ No paid service has been added; Groq and Gemini remain on free tier
- ✅ All new tests pass; retrieval NDCG@10 is measured and recorded
- ✅ All existing tests still pass

---

## PART 5 — WHAT IS EXPLICITLY OUT OF SCOPE

Do not implement any of the following, even if it seems easy or related:

- Reels, short-form video, meme, or TTS generation (Phase 5)
- Image generation (Phase 5)
- Collaboration / workspaces / `workspace_id` (Phase 4)
- Personal memory layer or recommendation system (Phase 4)
- Semantic alerts (depends on memory layer)
- Automation rule engine (Phase 4)
- Playwright for JS-heavy sites (revisit if real usage shows a gap)
- FSRS scheduler (SM-2 is sufficient for MVP)
- Mobile app
- Public sharing
- Multi-tenancy
- Docker or cloud deployment

---

## PART 6 — MIGRATION ORDER REFERENCE

| # | Name | Sub-phase | Tables/columns |
|---|---|---|---|
| 0008 | chunk_tsvector | 3.1 | `chunks.tsv` column + GIN index |
| 0009 | url_documents | 3.3 | `documents.source_url`, `.captured_at`, `.extension_capture`, `.media_type` |
| 0010 | notion_state | 3.3 | `notion_integrations`, `notion_pages` |
| 0011 | audio_segments | 3.3 | `audio_segments` |
| 0012 | annotations | 3.5 | `annotations` |
| 0013 | flashcards | 3.6 | `flashcards`, `flashcard_reviews` |

Numbers are sequential by sub-phase execution order. Do not create migration
0010 before 0009 is applied.

---

## PART 7 — NEW CELERY QUEUES (final state after Phase 3)

```powershell
# scripts/start-worker.ps1 — final command
celery -A app.workers.celery_app worker --pool=solo `
  --queues=default,ner,intelligence,claims,nli,credibility,ocr,transcription,cards
```

| Queue | Status | Tasks |
|---|---|---|
| `default` | Phase 1 | parse, chunk, embed |
| `ner` | Phase 2 | extract_entities, extract_relations, create_user_insight (new 3.5) |
| `intelligence` | Phase 2 | generate_intelligence, assign_topics, auto_title_conversation (new 3.2), notion_sync (new 3.3) |
| `claims` | Phase 2.5 | extract_claims |
| `nli` | Phase 2.5 | detect_contradictions |
| `credibility` | Phase 2.5 | compute_credibility, recompute_cohort |
| `ocr` | **New 3.3** | run_ocr, ocr_preprocess |
| `transcription` | **New 3.3** | transcribe_audio, fetch_youtube_transcript |
| `cards` | **New 3.6** | generate_cards |

---

*End of Phase 3 Prompt. Start with PART 0 orientation before writing any code.*
