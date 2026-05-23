# NexusMind — Phase 3 Prompts for Claude Code

Paste the **Kickoff Prompt** first when you start Phase 3. Then use the
per-sub-phase prompts (3.1 through 3.7) as you complete each one. They are
designed to be used in order, but 3.4 and 3.7 can run in parallel.

Each prompt is self-contained — it references the plan file and tells Claude
Code what to read before doing anything.

---

## 0. Kickoff Prompt (paste this once at the start of Phase 3)

```
You are working on NexusMind — a personal AI knowledge graph system built with
FastAPI + Celery + PostgreSQL/pgvector + Next.js. Phases 1, 2, and 2.5 are
complete. We are starting Phase 3 now.

Before doing anything else, read these files in this order:

1. NexusMind_Phase2_5_Changes.md (root of repo or wherever the planning docs
   live). This is the authoritative description of what actually got built,
   which differs significantly from the original PDF specs. Pay particular
   attention to:
   - Section 1 (no Docker, local filesystem storage, no MinIO/S3)
   - Section 2 (Gemini 768-dim embeddings, Groq llama-3.3-70b, Ollama qwen2.5
     local — NOT OpenAI/Cohere)
   - Section 3 (mixed /api prefix scheme — Phase 1 routes are unprefixed,
     Phase 2+ routes are under /api)
   - Section 5 (six existing Celery queues)
   - Section 7 (the items NOT yet implemented — these are the Phase 3 starting
     point)
   - Section 13 (actual env vars in use)

2. NexusMind_Phase3_Plan.md. This is the plan we are now executing. Read the
   whole thing, but especially:
   - Section 0 (non-negotiable constraints)
   - Section 1 (the eight tracks)
   - Section 15 (the seven sub-phase ordering)
   - Section 19 (out of scope — do not implement these even if it seems easy)

3. The repo structure. Run `find . -type f -name "*.py" | head -50` and
   `find . -type f -name "*.tsx" | head -50` to get oriented. Read
   `backend/app/core/config.py`, `backend/app/workers/celery_app.py`, and
   `backend/alembic/versions/` to confirm current state.

Ground rules for all of Phase 3:

- ZERO paid services. If a library or API has a free tier, use it within free
  limits. If something needs a key, it must be one of: GROQ_API_KEY,
  GEMINI_API_KEY, or a personal Notion integration token the user provides.
  No OpenAI, no Cohere, no Sentry, no Anthropic, no ElevenLabs, no AWS.
- NO Docker. Native Windows binaries. PowerShell scripts to start services.
- NO cloud storage. All files go through the existing StorageService writing
  to DATA_DIR.
- 768-dim vectors on the chunk path. The HNSW index is vector(768). Never
  introduce a different dimension on chunks.
- Mixed API prefix scheme. New Phase 3 routes follow Phase 2 convention
  (under /api) UNLESS they are extending a Phase 1 unprefixed route (in
  which case match the existing prefix).
- Single-user-per-account. Do not add workspace_id.
- Every new feature gets at least one unit test and is documented in a
  README section under `docs/phase3/`.

Working agreement:

- Before writing code for a new sub-phase, write a short plan (5-10 bullets)
  of what files you'll create or change, then wait for me to approve.
- When you discover a contradiction between the plan and the actual codebase,
  flag it and ask — don't silently adapt.
- For each migration, generate the Alembic file but DO NOT run it. List the
  exact command for me to run.
- For each new dependency, run `pip install <pkg>` and update
  `backend/requirements.txt` (or the equivalent for the frontend). State the
  exact version that got pinned.
- Run existing tests after every meaningful change. If anything was passing
  before and now fails, stop and fix.
- Don't refactor code that isn't in scope for the current sub-phase.

When you have finished reading the three files above and the repo orientation,
tell me:
1. Confirmation that you found the Phase 2.5 changes doc and the Phase 3 plan
2. The current Alembic head (latest applied migration)
3. The Celery queues currently registered in celery_app.py
4. Anything that doesn't match what the Phase 2.5 changes doc claims is built

Wait for me to acknowledge before starting Phase 3.1.
```

---

## 1. Phase 3.1 Prompt — Hybrid Retrieval + Reranker + Search Page

```
Implement Phase 3.1: retrieval foundation (Tracks A + B in the plan).

Read these sections of NexusMind_Phase3_Plan.md first:
- Section 2 (Track A — Hybrid Retrieval + Local Reranker)
- Section 3 (Track B — Metadata Filters + Search Page)
- Section 15.3.1 (acceptance criteria for this sub-phase)

Deliverables, in this order:

1. Alembic migration `0008_chunk_tsvector`:
   - Add `tsv tsvector` column on `chunks`
   - GIN index on `tsv`
   - Trigger using `tsvector_update_trigger` on the `text` column
   - Backfill statement in the migration body
   - Provide the exact `alembic upgrade` command for me to run

2. Backend `services/retrieval.py` changes:
   - `bm25_search(query, user_id, top_k=50, filters=None)` returning chunk IDs
     ranked by `ts_rank_cd`
   - `rrf_merge(rank_lists, k=60)` per the plan
   - `rerank(query, chunks, top_k=10)` using `BAAI/bge-reranker-base` via
     sentence-transformers CrossEncoder
   - Lazy-load the reranker (module-level singleton, initialized on first call)
   - Honor a `RERANKER_ENABLED` env var (default: true) — when false, return
     RRF top-k directly
   - Updated `hybrid_search(query, filters, top_k)` orchestrating the full flow
     (vector top-50 + BM25 top-50 → RRF top-30 → rerank top-10)

3. Add `BAAI/bge-reranker-base` to dependencies. Use the sentence-transformers
   library already in the project if present; otherwise add it pinned. Verify
   the model downloads to the standard HuggingFace cache.

4. Update `/qa` endpoint:
   - Accept `filters` field in the request body (source_type, date_range,
     topic_tag, min_credibility, entity_id)
   - Apply filters at the SQL level before fusion, not after
   - Use the new hybrid retrieval path

5. New endpoint `POST /api/search`:
   - Same filter shape as /qa
   - Returns ranked chunks with: chunk text, document title, page, similarity
     score, credibility_score, source_type, topic tags
   - Add Redis caching with key = SHA-256(query || sorted_filters || top_k),
     TTL 5 minutes
   - On document ingestion completion, evict the entire search cache prefix

6. New Next.js page `/search`:
   - Search bar with 300ms debounce
   - Filter sidebar: source type chips, date-range picker, topic multi-select,
     credibility slider (0 to 1, step 0.1)
   - Result cards using existing CredibilityBadge component
   - Click result → navigate to /library/[id] with chunk anchor
   - URL-state filters (useSearchParams) so URLs are shareable
   - Highlighted snippet using mark.js (free, MIT)

7. Add navigation link "Search" to `app/(app)/layout.tsx`.

8. Tests:
   - `tests/test_bm25.py` — covers query path and tsvector trigger
   - `tests/test_rrf.py` — pure function tests with fixture rank lists
   - `tests/test_reranker.py` — mocked or with a tiny CrossEncoder; assert
     the order changes for a deliberately mis-ranked input
   - `tests/test_search_api.py` — integration test for /api/search with
     filter combinations
   - `tests/retrieval_eval.py` — uses `ranx` (free, MIT). Create ~20 to 30
     hand-labeled query-chunk relevance pairs in a JSON fixture. Compute
     NDCG@10 and MRR@10 against the new retrieval path. Don't enforce a
     threshold; just print the metrics so we can track them.

Definition of done:
- All new tests pass.
- Existing tests still pass (do not break test_qa.py).
- /qa returns answers using the new retrieval path; latency p95 under 4s with
  reranker, under 2.5s without.
- /search returns filtered results in under 800ms p95 on cached queries.
- NDCG@10 number is printed and recorded in docs/phase3/retrieval_baseline.md.

Before coding, give me your file-change plan.
```

---

## 2. Phase 3.2 Prompt — SSE Streaming + Conversation History

```
Implement Phase 3.2: SSE streaming and conversation history (Track C).

Read Section 4 of NexusMind_Phase3_Plan.md.

Deliverables:

1. Backend `services/llm.py`:
   - Add async `stream(prompt)` method on the Groq client wrapper.
     Groq's OpenAI-compatible API supports streaming; use the official `groq`
     or `openai` Python SDK in streaming mode (whichever is already in stack).
   - Preserve the existing non-streaming method.

2. New endpoint `GET /qa/stream`:
   - Query params for query, conversation_id (optional), filters (JSON-encoded)
   - Returns FastAPI `StreamingResponse` with media type `text/event-stream`
   - Emits events: `token` (per token), `citations` (after stream completes),
     `no_source` (if retrieval below QA_NO_SOURCE_THRESHOLD — emitted and
     stream ends without invoking the LLM), `done` (final marker)
   - Sets `X-Accel-Buffering: no` and `Cache-Control: no-cache` headers
   - Note: this is GET, not POST, so EventSource can connect natively

3. Conversation persistence:
   - Reuse existing `conversations` and `messages` tables (Phase 1 schema —
     verify they exist; if not, this is the time to add them)
   - On every /qa or /qa/stream call: if no conversation_id provided, create
     one. Append the user message and the assistant response (after stream
     completes) to messages.
   - Sliding window memory: when assembling the LLM prompt, include the last
     6 messages from the conversation (3 user + 3 assistant turns max).

4. New endpoints:
   - `GET /api/conversations` — paginated list, newest first
   - `GET /api/conversations/{id}` — full message thread
   - `PATCH /api/conversations/{id}` — rename (title field)
   - `DELETE /api/conversations/{id}`

5. Frontend `/qa` page:
   - Collapsible left sidebar listing conversations
   - "New conversation" button
   - Click conversation → load messages
   - Inline rename (double-click title)
   - Streaming message component using native EventSource — no library
   - Citation chips appear after the stream completes (when the `citations`
     event arrives)

6. Auto-title conversations:
   - After the first assistant response, call Ollama (free, local) to generate
     a 4-6 word title from the first user message. Update the conversation
     title.
   - Do not block the user-visible stream on this — fire it as a Celery task
     on the `intelligence` queue.

7. Tests:
   - `tests/test_qa_stream.py` — integration test that connects to the SSE
     endpoint, collects events, asserts the expected sequence
   - `tests/test_conversations.py` — CRUD coverage
   - `tests/test_sliding_window.py` — assert that 7+ messages get truncated
     to 6 when building the prompt

Definition of done:
- First token appears in the UI within 600ms of submitting a query on cached
  retrieval (within 1.5s on cold).
- Conversations persist across page reloads.
- Rename and delete work.
- Existing /qa tests still pass.

Plan first, then code.
```

---

## 3. Phase 3.3 Prompt — Multi-Source Ingestion

```
Implement Phase 3.3: multi-source ingestion (Track D).

Read Section 5 of NexusMind_Phase3_Plan.md.

Deliverables in order:

1. Migrations:
   - `0009_url_documents`: add columns to `documents`:
     `source_url TEXT`, `captured_at TIMESTAMPTZ`,
     `extension_capture BOOLEAN DEFAULT FALSE`,
     `media_type TEXT` (one of: text, web, audio, video, notion)
   - `0012_notion_state`: tables `notion_integrations` (id, user_id,
     token_encrypted, workspace_name, created_at) and `notion_pages`
     (page_id PK, integration_id FK, document_id FK, notion_last_edited_at,
     last_synced_at)
   - `0013_audio_segments`: `audio_segments` (id, chunk_id FK,
     start_seconds FLOAT, end_seconds FLOAT, index for chunk_id)

2. Web URL ingestion:
   - `pip install trafilatura` (pinned version)
   - New endpoint `POST /ingest/url` body `{ url }`
   - Celery task on the `default` queue: fetch with httpx (15s timeout,
     follow redirects, User-Agent "NexusMind/1.0"), extract with
     `trafilatura.extract` (include_links=True, include_tables=True,
     output_format='txt'), pull metadata with `trafilatura.extract_metadata`
   - Write a text file to DATA_DIR (so storage contract is uniform)
   - Dedupe via SHA-256 of canonical URL (same as upload dedupe by content
     hash; new column or use existing content_hash with the URL as input)
   - Reject if extracted text < 200 chars with an explanatory error
   - Route into the standard parse → chunk → embed → ner → ... pipeline

3. OCR pipeline integration:
   - Verify Tesseract 5 is installed: `tesseract --version`. If not, log
     a clear warning at API startup and gracefully degrade (documents marked
     "OCR unavailable" in the intelligence pane).
   - `pip install pytesseract pillow`
   - New Celery queue `ocr`
   - In the parse worker, after pypdf extraction, compute average chars/page.
     If under 100, route the document to `ocr` queue.
   - OCR worker: render each page to PNG via PyMuPDF (`fitz`), preprocess
     with Pillow (grayscale + Otsu threshold + deskew), run pytesseract,
     replace the document's extracted text with the OCR output.
   - Add an `ocr_quality` field on documents (low / medium / high) based on
     simple heuristics: average word length, ratio of recognized words to
     non-words.

4. Audio transcription:
   - `pip install faster-whisper`
   - Verify ffmpeg is installed; warn at startup if not.
   - Extend ALLOWED_MIME_TYPES to include audio/mpeg, audio/wav, audio/m4a,
     audio/ogg, video/mp4
   - New endpoint `POST /ingest/audio` accepting multipart upload up to 500MB
     (override MAX_UPLOAD_BYTES for this endpoint only — don't change the
     global)
   - New Celery queue `transcription`
   - Worker: use faster-whisper `base.en` model, device="cpu",
     compute_type="int8", beam_size=5, vad_filter=True
   - Stitch segments into a single text document with per-segment timestamps
     stored in `audio_segments` linked to chunks
   - For video/mp4: extract audio first via ffmpeg subprocess call

5. YouTube transcripts:
   - `pip install youtube-transcript-api yt-dlp`
   - New endpoint `POST /ingest/youtube` body `{ url }`
   - Worker: try `YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])`,
     fall back to auto-generated, fall back to `yt-dlp` audio extraction →
     faster-whisper transcription
   - Metadata via yt-dlp: title, channel, upload_date, duration
   - Store as a text document with timestamps in audio_segments

6. Notion connector:
   - `pip install notion-client notion-to-md` (verify notion-to-md is the
     right Python lib name; if not, equivalent free package)
   - New endpoints:
     - `POST /notion/connect` body `{ token, workspace_name }` — encrypt the
       token at rest using the existing JWT_SECRET as key (Fernet from
       `cryptography` is fine), store in notion_integrations
     - `POST /notion/sync` — sync now (returns job_id)
     - `POST /notion/schedule` body `{ hours }` — set up Celery beat schedule
       at this interval
     - `DELETE /notion/connect/{id}` — revoke
   - Worker: iterate databases the integration can see, pull pages, convert
     blocks to markdown, sleep 350ms between API calls to respect Notion
     rate limits
   - Idempotency: only re-ingest pages where `notion_last_edited_time` is
     newer than `last_synced_at`

7. Bulk ZIP import:
   - New endpoint `POST /ingest/zip` accepting upload up to MAX_UPLOAD_BYTES
   - Worker validates: no path traversal (`../`), entries match
     ALLOWED_MIME_TYPES
   - Enqueue one parse job per supported entry
   - Skip unsupported entries with a warning in the response

8. Worker startup script update:
   - Update `scripts/start-worker.ps1` to include `ocr` and `transcription`
     queues (the full list becomes: default,ner,intelligence,claims,nli,
     credibility,ocr,transcription — `cards` comes in 3.6)

9. Frontend `/upload` page additions:
   - Three new tabs alongside File Upload: URL, Audio, YouTube
   - New page `/connections` for Notion connect and ZIP import
   - Show ingestion status with the same polling mechanism as file uploads

10. Tests:
    - One integration test per source: test_ingest_url.py,
      test_ingest_audio.py (use a 5-second fixture audio file),
      test_ingest_youtube.py (mock the transcript API),
      test_ingest_notion.py (mock the Notion SDK), test_ingest_zip.py
    - test_ocr.py — feed a known scanned-PDF fixture, assert text extracted

Definition of done:
- All five source types successfully ingest representative samples.
- Dedupe works per source.
- Timestamped citations show for audio and YouTube in /qa responses (you
  can verify this by querying the audio document and seeing "at 03:42" in
  the answer).
- Tesseract and ffmpeg unavailability gracefully degrade rather than crash.
- All new tests pass; existing tests still pass.

Plan the file changes first.
```

---

## 4. Phase 3.4 Prompt — Browser Extension

```
Implement Phase 3.4: browser extension (Track E).

Read Section 6 of NexusMind_Phase3_Plan.md.

This is a separate project living under `extension/` at the repo root, not
inside the existing `frontend/` Next.js app.

Deliverables:

1. Scaffold:
   - Create `extension/` directory
   - `npm init`, `npm install -D vite vite-plugin-web-extension typescript
     @types/chrome` (pinned)
   - `npm install react react-dom @mozilla/readability webextension-polyfill`
   - Tailwind setup if you want it, otherwise vanilla CSS for the popup
   - `manifest.json` with Manifest V3:
     - permissions: activeTab, contextMenus, storage, scripting
     - host_permissions: `<all_urls>`
     - background service worker, content scripts, popup, options page

2. Content script (`src/content/main.ts`):
   - When invoked, run Readability.js on `document.cloneNode(true)` (the
     standard pattern — Readability modifies the DOM)
   - Send extracted article (title, content, textContent, byline, length) to
     the background service worker

3. Background service worker (`src/background/main.ts`):
   - Listen for toolbar button click → inject content script → receive
     article → POST to `/ingest/url-content` with stored JWT
   - Listen for context menu click on selected text → POST selection plus
     1-2 surrounding sentences to `/api/notes/highlight`
   - Show notification on success or failure

4. Popup (`src/popup/Popup.tsx`):
   - Top: status (logged in as / not logged in)
   - Search box → hits `/api/search` (use the endpoint built in Phase 3.1)
   - Recent saves list (last 10 from `/api/documents?limit=10`)
   - Settings link to the options page

5. Options page (`src/options/Options.tsx`):
   - Base URL (default http://localhost:8000)
   - Token paste field
   - "Test connection" button hitting `/auth/me`
   - Revoke / clear local data button

6. Backend endpoints to add:
   - `POST /ingest/url-content` body `{ url, title, content, byline,
     captured_at }` — accept pre-extracted content from the extension, skip
     the trafilatura fetch step but otherwise route through the standard
     pipeline. The frontend already passes `extension_capture=true` so set
     that column.
   - `POST /api/notes/highlight` body `{ url, highlighted_text, context,
     title }` — create a stub Document if the URL doesn't exist, then create
     an annotation pointing at it (this anticipates Phase 3.5; if 3.5 is not
     yet done, create just the document for now and add a TODO comment to
     wire the annotation when 3.5 lands).
   - `GET /api/extension/token` in the web app — issue a long-lived JWT
     (90-day TTL) scoped to ingest and search endpoints only

7. Web app `/connections` page additions:
   - Show extension token (masked by default, click to reveal)
   - "Regenerate" button (invalidates old token)
   - Install instructions: link to chrome://extensions, instructions for
     loading unpacked, paste-token flow

8. Build and load:
   - `npm run build` produces `extension/dist/`
   - Document the loading process in `docs/phase3/extension_install.md`:
     Chrome (chrome://extensions, developer mode, Load unpacked), Firefox
     (about:debugging, Load Temporary Add-on)

9. Tests:
   - At minimum, smoke test the popup search box against a running backend
     (this is hard to fully automate without Playwright; document manual
     test steps in extension_install.md)
   - Backend test for `/ingest/url-content` and `/api/extension/token`

Definition of done:
- Extension loads unpacked in Chrome and Firefox.
- Toolbar button saves the current article and it shows up in /library
  within 15 seconds.
- Right-click on selected text creates an annotation (or document stub if
  3.5 not yet shipped).
- Popup search returns hits from the user's library.

Plan first.
```

---

## 5. Phase 3.5 Prompt — Notes & Annotation System

```
Implement Phase 3.5: notes and annotation system (Track F).

Read Section 7 of NexusMind_Phase3_Plan.md.

Deliverables:

1. Migration `0010_annotations`:
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

2. Endpoints:
   - `POST /api/annotations` — create
   - `GET /api/annotations` — list with filters: ?document_id, ?tag, ?from,
     ?to, pagination
   - `PATCH /api/annotations/{id}` — edit note, tags, color
   - `DELETE /api/annotations/{id}`
   - `GET /api/annotations/export?format=md|csv` — return markdown or CSV
     of all annotations for the user

3. Graph integration:
   - On annotation create where `note` is non-empty:
     - Create a new entity with type `user_insight`
     - Use the note text as the entity name; embed via the existing
       `entity_embedding` service (all-MiniLM-L6-v2)
     - Create an `entity_edge` with type `relates_to` and confidence 1.0
       from the user_insight to each entity already linked to the source
       chunk
   - Run this as a Celery task on the `ner` queue (it's already entity work)
   - In the graph explorer, render `user_insight` nodes with a distinct
     color (suggest: amber) and a small pencil icon

4. Retrieval integration:
   - Index annotations as chunks in the vector store with
     `source_type='user_annotation'`
   - This means annotations appear in /qa and /api/search results
   - Filter chip for "user_annotation" source type works out of the box
     since Phase 3.1 already supports source_type filters

5. Frontend:
   - `components/annotations/HighlightOverlay.tsx` mounted on
     `/library/[id]` document viewer
     - Uses `window.getSelection()` and `Range.getBoundingClientRect()`
     - Shows a floating popover with: color picker, note textarea, tag
       input, save/cancel buttons
     - On save, sends to `/api/annotations` with char_start/char_end derived
       from the selection range in the rendered text
   - `components/annotations/AnnotationCard.tsx` for the /notes page
   - New page `/notes`:
     - List of all annotations
     - Filter sidebar: tag multi-select, document filter, date range
     - Click annotation → navigate to /library/[id] scrolled to the chunk
       with the highlight re-rendered
     - "Export" dropdown with Markdown / CSV options

6. Persistence of highlights:
   - When the document viewer renders, fetch all annotations for that
     document and apply highlight spans at the char_start/char_end ranges
   - Different colors render with different background colors
   - Hover over highlight → show note preview tooltip
   - Click highlight → open the annotation card in a side panel for edit

7. Tests:
   - test_annotations_crud.py — full CRUD
   - test_annotations_graph.py — assert user_insight entity and edges are
     created on annotation save
   - test_annotations_retrieval.py — assert annotations surface in search
     results when source_type filter includes user_annotation
   - test_annotations_export.py — markdown and CSV format checks

Wire the `/api/notes/highlight` endpoint stub from Phase 3.4 into this real
annotations pipeline. Update its TODO comment to a real implementation.

Definition of done:
- Highlights persist across page reloads and re-render correctly.
- Annotations appear as user_insight nodes in the graph explorer with edges
  to source-chunk entities.
- Annotations surface in /qa retrieval when the source_type filter allows.
- Markdown and CSV exports produce valid output.

Plan first.
```

---

## 6. Phase 3.6 Prompt — Spaced Repetition

```
Implement Phase 3.6: spaced repetition flashcards (Track G).

Read Section 8 of NexusMind_Phase3_Plan.md.

Deliverables:

1. Migration `0011_flashcards`:
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
   CREATE INDEX cards_user_due ON flashcards(user_id, due_date)
       WHERE NOT suspended;

   CREATE TABLE flashcard_reviews (
       id           UUID PRIMARY KEY,
       card_id      UUID NOT NULL REFERENCES flashcards(id) ON DELETE CASCADE,
       rating       SMALLINT NOT NULL,
       reviewed_at  TIMESTAMPTZ DEFAULT now()
   );
   ```

2. SM-2 implementation:
   - New file `backend/app/services/srs.py`
   - Pure function `sm2(card_state, rating)` returning updated state per the
     plan (Section 8.2)
   - Ratings: 0=Again, 1=Hard, 2=Good, 3=Easy
   - Unit test all four ratings against expected interval/ease transitions

3. Card generation worker:
   - New Celery queue `cards`
   - New task `generate_cards(document_id)` on `cards` queue
   - For each chunk in the document, call Ollama with the JSON-mode prompt
     from Section 8.1. Use the existing `services/llm_local.py` client.
   - Insert resulting cards in `flashcards` table
   - Make this opt-in: do not run automatically after intelligence completes.
     Only run when the user clicks "Generate cards" on a document, or when
     they enable a global setting `auto_generate_cards`.

4. Endpoints:
   - `POST /api/cards/generate` body `{ document_id }` — kick off the task,
     return job_id
   - `GET /api/cards/due` — cards where due_date <= today and not suspended
   - `POST /api/cards/{id}/review` body `{ rating: 0..3 }` — apply SM-2,
     persist to flashcards and flashcard_reviews, return new state
   - `GET /api/cards` — list all user's cards with pagination and filters
     (document_id, suspended)
   - `PATCH /api/cards/{id}` — edit question, answer, or set suspended
   - `DELETE /api/cards/{id}`
   - `GET /api/cards/stats` — return:
     - cards_total
     - cards_due_today
     - cards_mastered (reps >= 3)
     - current_streak (consecutive days with at least one review)
     - reviews_last_7_days (count)

5. Worker startup script update:
   - Add `cards` to the queue list in `scripts/start-worker.ps1`
     Final queue list: default,ner,intelligence,claims,nli,credibility,
     ocr,transcription,cards

6. Frontend:
   - New page `/flashcards`:
     - Hero: due-today count and "Start review" button
     - Stats: streak, mastery %, total cards
     - Recent activity chart (last 30 days reviews per day) — use existing
       Recharts setup if present
   - `components/cards/ReviewModal.tsx`:
     - Card front (question), tap or space to flip
     - Card back (answer) with four rating buttons + source chunk link
     - Keyboard shortcuts: 1=Again, 2=Hard, 3=Good, 4=Easy
     - CSS 3D flip animation
     - Auto-advance to next card after rating
   - Per-document panel on `/library/[id]`:
     - "Generate cards" button (idempotent — only generates new ones for
       chunks without existing cards)
     - List of cards for this document with edit/delete/suspend actions

7. Browser notifications:
   - Service worker that registers a periodic check (chrome's
     `chrome.alarms` API for the browser extension is one option, but for
     the main web app use a simple `setInterval` in the layout component
     that pings `/api/cards/stats` every hour)
   - When cards_due_today > 0 and notifications are permitted, show a
     browser notification linking to /flashcards
   - Settings toggle to enable/disable

8. Tests:
   - test_sm2.py — all four ratings, edge cases (reps=0, reps=1, reps>1),
     ease floor at 1.3
   - test_cards_generation.py — mock Ollama to return a fixed JSON, assert
     cards land in the database
   - test_cards_review.py — submit each rating, assert next due_date and
     state
   - test_cards_stats.py — fixture data, assert all stat fields

Definition of done:
- Card generation produces valid cards for a test document.
- All four SM-2 ratings transition state correctly per the algorithm.
- Review UI works end-to-end with keyboard shortcuts.
- Browser notification fires when there are due cards (manually verified).
- Stats endpoint returns correct values for a seeded dataset.

Plan first.
```

---

## 7. Phase 3.7 Prompt — Grafana Dashboards (can run in parallel with 3.4+)

```
Implement Phase 3.7: Grafana dashboards (Track H).

Read Section 9 of NexusMind_Phase3_Plan.md.

This is mostly configuration, no application code changes (except possibly
adding a few Prometheus counters that don't yet exist).

Deliverables:

1. Confirm Prometheus is scraping:
   - Read `backend/app/api/metrics.py` and `backend/app/core/metrics.py`
   - List existing Prometheus metrics
   - Verify Prometheus itself is running locally (default port 9090)
   - If Prometheus isn't installed, write `scripts/install-prometheus.ps1`
     that downloads the Windows binary, writes `prometheus.yml` scraping
     `http://localhost:8000/metrics`, and starts Prometheus as a Windows
     service via NSSM or as a scheduled task

2. Add missing metrics (only if not already present):
   - `nexusmind_celery_queue_depth{queue}` — gauge per queue, updated by a
     periodic Celery task that calls `redis-cli llen celery:<queue>`
   - `nexusmind_celery_task_duration_seconds{task,queue}` — histogram
   - `nexusmind_celery_task_failures_total{task,queue}` — counter
   - `nexusmind_retrieval_duration_seconds{stage}` — histogram with stages:
     vector, bm25, rrf, rerank
   - `nexusmind_retrieval_cache_hits_total` and `..._misses_total`
   - `nexusmind_llm_requests_total{provider,model}` — counter
   - `nexusmind_llm_tokens_total{provider,model,direction}` — counter,
     direction in (prompt, completion)
   - `nexusmind_llm_duration_seconds{provider,model}` — histogram
   - `nexusmind_ingestion_status_total{source_type,status}` — counter,
     status in (queued, parsing, complete, failed)

3. Install Grafana OSS:
   - Write `scripts/install-grafana.ps1` that downloads the Windows binary,
     writes a minimal `defaults.ini` with Prometheus datasource provisioning,
     and starts Grafana on port 3001 (3000 is taken by the Next.js dev
     server)
   - Default credentials documented in `docs/phase3/observability.md`

4. Provision dashboards via JSON files committed to repo:
   - `ops/grafana/dashboards/ingestion.json`:
     - Queue depth per queue (time series)
     - Task duration p50/p95/p99 (time series)
     - Task failure rate (time series)
     - Ingestion success vs failure by source type (bar gauge)
   - `ops/grafana/dashboards/retrieval.json`:
     - /qa and /api/search request rate
     - Latency p50/p95/p99 per stage (vector, bm25, rrf, rerank)
     - Cache hit ratio (single stat)
   - `ops/grafana/dashboards/ai_usage.json`:
     - Groq tokens per hour (running total against free tier limit)
     - Gemini embedding requests per hour
     - Ollama request count and average latency
     - LLM error rate
   - `ops/grafana/dashboards/system.json`:
     - CPU and memory usage (use node_exporter if installed; otherwise
       skip and document)
     - DATA_DIR disk usage
     - Postgres connection count
     - Redis memory usage

5. Provisioning configuration:
   - `ops/grafana/provisioning/datasources/prometheus.yaml`
   - `ops/grafana/provisioning/dashboards/dashboards.yaml` pointing to the
     dashboards folder

6. Documentation:
   - `docs/phase3/observability.md`:
     - How to start Prometheus + Grafana
     - URLs and default creds
     - Screenshot/diagram of each dashboard (optional)
     - How to add a new metric
     - How to add a new dashboard panel

7. Tests:
   - Add a single test that hits `/metrics` and asserts the new metrics
     are present in the output

Definition of done:
- Grafana is reachable at http://localhost:3001 with the Prometheus
  datasource pre-configured
- All four dashboards render with live data after the system has been used
  for at least an hour
- New metrics are exported and visible in /metrics output

Plan first.
```

---

## How to Use These Prompts

1. Start a Claude Code session in your project root.
2. Paste the Kickoff Prompt. Let Claude Code read the docs and orient itself.
3. After it reports back, paste the Phase 3.1 prompt. Let it plan, approve
   its plan, then let it implement.
4. After 3.1 is verified and committed, paste 3.2. Repeat.
5. Phase 3.4 (extension) and 3.7 (Grafana) can run in parallel branches
   alongside 3.5 or 3.6 if you want to context-switch.
6. After all seven sub-phases are done, run the full Phase 3 acceptance
   checklist from Section 16 of the plan.

### Working with Claude Code

- Each prompt ends with "Plan first." Honor that — don't let it skip
  planning. The plans catch ambiguity early.
- If Claude Code asks for clarification, answer it. Don't tell it to just
  pick something — the constraints (free-only, no Docker, 768-dim) mean
  the wrong default can be hard to unwind.
- Commit after every sub-phase. Tag commits like `phase-3.1-complete` so
  rollback is clean.
- Run tests yourself after every sub-phase. Don't trust "tests pass" without
  verifying.

### If you only have time for the high-impact half

Skip in this order:
- 3.7 (Grafana) — observability nice-to-have
- 3.4 (Extension) — only matters if you actually browse a lot
- 3.6 (Spaced repetition) — useful but not foundational

Keep at minimum: 3.1, 3.2, 3.3, 3.5. That gives you good retrieval, streaming
chat, all five source types, and annotations — which is the meaningful
upgrade over current Phase 2.5 state.
