# SourceWeave — Phase 1 MVP Build Prompt

## System Context

You are an expert full-stack AI engineer building **SourceWeave**, a personal AI knowledge
management platform.

SourceWeave is NOT a chatbot wrapper. It is a document intelligence system that:

- ingests files
- extracts and normalizes text
- chunks content semantically
- generates embeddings
- stores vectors in PostgreSQL with pgvector
- performs semantic retrieval
- answers questions grounded strictly in retrieved document excerpts

This prompt covers ONLY **Phase 1: Foundation MVP**.
Do NOT implement features from later phases (knowledge graph, OCR, browser extension,
collaboration, hybrid search, streaming, etc.).

Every design decision must prioritize:

- correctness
- reliability
- maintainability
- security
- working infrastructure

over visual polish or unnecessary abstraction.

---

## Required Build Order

Implement the system in this exact sequence. Do not skip ahead before previous stages
are functional and verified.

1. Docker infrastructure
2. Database models + Alembic migrations
3. Authentication
4. File upload pipeline
5. Celery workers
6. Embedding pipeline
7. Semantic search
8. Q&A endpoint
9. Frontend authentication
10. Upload UI
11. Search UI
12. Q&A UI
13. Error handling + observability
14. Final integration testing

---

## Project Structure

```txt
sourceweave/
├── backend/
│   ├── app/
│   │   ├── api/                    # FastAPI route handlers
│   │   │   ├── __init__.py
│   │   │   ├── auth.py             # /auth/register, /auth/token, /auth/me
│   │   │   ├── documents.py        # /ingest, /documents, /documents/{id}
│   │   │   ├── search.py           # /search
│   │   │   ├── qa.py               # /qa
│   │   │   └── health.py           # /health, /readiness
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── jwt.py              # encode/decode JWTs
│   │   │   ├── password.py         # bcrypt hashing
│   │   │   └── dependencies.py     # get_current_user FastAPI dep
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # Pydantic Settings from env
│   │   │   ├── logging.py          # structlog setup
│   │   │   └── exceptions.py       # custom exception classes
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── session.py          # async SQLAlchemy engine + session
│   │   │   └── base.py             # Declarative Base
│   │   ├── models/                 # SQLAlchemy ORM models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── document.py
│   │   │   ├── chunk.py
│   │   │   ├── conversation.py
│   │   │   └── message.py
│   │   ├── schemas/                # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── document.py
│   │   │   ├── search.py
│   │   │   └── qa.py
│   │   ├── services/               # business logic, no HTTP concerns
│   │   │   ├── __init__.py
│   │   │   ├── storage.py          # MinIO/S3 wrapper
│   │   │   ├── embedding.py        # OpenAI embedding client
│   │   │   ├── llm.py              # LLM call + citation parsing
│   │   │   ├── retrieval.py        # vector search
│   │   │   └── chunking.py         # text splitter
│   │   ├── workers/                # Celery tasks
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   ├── parse.py
│   │   │   ├── chunk.py
│   │   │   └── embed.py
│   │   ├── utils/
│   │   │   ├── __init__.py
│   │   │   └── text.py             # ftfy + normalization helpers
│   │   └── main.py                 # FastAPI app factory
│   ├── alembic/
│   │   ├── versions/
│   │   ├── env.py
│   │   └── alembic.ini
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_auth.py
│   │   ├── test_ingest.py
│   │   ├── test_search.py
│   │   └── test_qa.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── app/                        # Next.js App Router
│   │   ├── (auth)/
│   │   │   ├── sign-in/page.tsx
│   │   │   └── sign-up/page.tsx
│   │   ├── (app)/
│   │   │   ├── layout.tsx          # sidebar shell, requires auth
│   │   │   ├── page.tsx            # dashboard
│   │   │   ├── upload/page.tsx
│   │   │   ├── search/page.tsx
│   │   │   ├── qa/page.tsx
│   │   │   └── library/page.tsx
│   │   ├── api/auth/[...nextauth]/route.ts
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/
│   │   ├── ui/                     # primitives (button, input, badge)
│   │   ├── upload/
│   │   ├── search/
│   │   ├── qa/                     # chat bubble, citation popover
│   │   └── library/
│   ├── hooks/
│   │   ├── useDocuments.ts
│   │   ├── useSearch.ts
│   │   └── useQA.ts
│   ├── lib/
│   │   ├── api-client.ts           # fetch wrapper attaching JWT
│   │   └── utils.ts
│   ├── services/                   # typed API service modules
│   │   ├── documents.ts
│   │   ├── search.ts
│   │   └── qa.ts
│   ├── types/
│   │   └── api.ts                  # shared API types
│   ├── middleware.ts               # NextAuth route protection
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Technology Stack (Phase 1 Only — No Substitutions)

| Layer | Technology | Version |
| --- | --- | --- |
| Backend framework | FastAPI | 0.111+ |
| Python | CPython | 3.11+ |
| ORM | SQLAlchemy (async) | 2.0+ |
| Migrations | Alembic | latest |
| Task queue | Celery | 5.x |
| Message broker | Redis | 7.x |
| Validation | Pydantic | v2 |
| PDF parsing | pdfplumber | latest |
| Encoding repair | ftfy | latest |
| Language detection | langdetect | latest |
| Text splitter | LangChain `RecursiveCharacterTextSplitter` | latest |
| Embedding model | OpenAI `text-embedding-3-small` | 1536-dim |
| LLM | OpenAI `gpt-4o-mini` | latest |
| Vector index | pgvector with HNSW | 0.7+ |
| Database | PostgreSQL | 16 |
| Object storage | MinIO (S3-compatible) | latest |
| Password hashing | bcrypt (passlib) | cost 12 |
| Frontend framework | Next.js (App Router) | 14 |
| Language | TypeScript | 5.x |
| Styling | Tailwind CSS | 3.x |
| Auth | NextAuth.js (Credentials provider) | 5.x |
| Server state | TanStack Query | v5 |
| Error tracking | Sentry (frontend + backend) | latest |
| Structured logs | structlog | latest |
| Container runtime | Docker + Docker Compose | latest |

Do not introduce alternative libraries (LlamaIndex, Pinecone, Qdrant, Supabase, Drizzle,
Prisma, etc.) at this phase. They are explicitly deferred.

---

## Environment Variables (`.env.example`)

```bash
# --- Database ---
DATABASE_URL=postgresql+asyncpg://postgres:password@postgres:5432/sourceweave
DATABASE_SYNC_URL=postgresql://postgres:password@postgres:5432/sourceweave   # for Alembic

# --- Cache + Broker ---
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# --- Object storage (MinIO local / S3 prod) ---
S3_ENDPOINT_URL=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=sourceweave-files
S3_REGION=us-east-1

# --- AI ---
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.1

# --- Retrieval thresholds ---
SEARCH_TOP_K_DEFAULT=5
QA_NO_SOURCE_THRESHOLD=0.6
SEARCH_LOW_CONFIDENCE_THRESHOLD=0.5

# --- Auth ---
JWT_SECRET=replace-with-32-byte-random-string
JWT_ALGORITHM=HS256
JWT_EXPIRY_SECONDS=3600

# --- Limits ---
MAX_UPLOAD_BYTES=52428800            # 50 MB
ALLOWED_MIME_TYPES=application/pdf,text/plain,text/markdown

# --- Frontend ---
NEXTAUTH_SECRET=replace-with-32-byte-random-string
NEXTAUTH_URL=http://localhost:3000
NEXT_PUBLIC_API_URL=http://localhost:8000

# --- Observability ---
SENTRY_DSN_BACKEND=
SENTRY_DSN_FRONTEND=
LOG_LEVEL=INFO
ENVIRONMENT=development
```

---

# Build Steps

Each step below contains its full specification. Implement and verify each step
before moving to the next.

---

## Step 1 — Docker Infrastructure

Create `docker-compose.yml` at the repo root with these services:

- **postgres** — image `pgvector/pgvector:pg16`, port `5432`, named volume `pgdata`
- **redis** — image `redis:7-alpine`, port `6379`
- **minio** — image `minio/minio`, ports `9000` (API) and `9001` (console),
  named volume `miniodata`, command `server /data --console-address ":9001"`
- **api** — built from `./backend`, port `8000`, depends on postgres / redis / minio,
  command `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- **worker** — built from `./backend`, depends on postgres / redis / minio,
  command `celery -A app.workers.celery_app worker --loglevel=info --concurrency=2`
- **frontend** — built from `./frontend`, port `3000`, command `npm run dev`

Requirements:

- All services share an `env_file: .env`
- `api` and `worker` mount `./backend:/app` for hot reload in dev
- `frontend` mounts `./frontend:/app` with an anonymous volume for `/app/node_modules`
- Add a `minio-init` one-shot service (or entrypoint script) that creates the bucket
  `sourceweave-files` on startup

**Verification:** `docker compose up` brings up all six services without errors.
`curl localhost:8000/health` returns `200` once the API is implemented (Step 13).

---

## Step 2 — Database Models + Alembic Migrations

Enable the pgvector extension in the first migration:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Create the following SQLAlchemy models. Every model uses UUID primary keys
(`gen_random_uuid()`), timezone-aware timestamps, and `ON DELETE CASCADE` foreign keys.

### `users`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` PK | default `gen_random_uuid()` |
| `email` | `TEXT` UNIQUE NOT NULL | lowercased on write |
| `password_hash` | `TEXT` NOT NULL | bcrypt |
| `created_at` | `TIMESTAMPTZ` | default `now()` |

### `documents`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → users | CASCADE |
| `filename` | `TEXT` NOT NULL | |
| `source_type` | `TEXT` NOT NULL | `pdf` / `txt` / `md` |
| `mime_type` | `TEXT` NOT NULL | |
| `file_size_bytes` | `BIGINT` | |
| `content_hash` | `TEXT` | SHA-256 of file bytes; used for dedup per user |
| `storage_path` | `TEXT` NOT NULL | `{user_id}/{document_id}/{filename}` |
| `processing_status` | `TEXT` | enum: `queued`, `parsing`, `chunking`, `embedding`, `complete`, `failed` |
| `error_message` | `TEXT` | nullable |
| `word_count` | `INT` | |
| `chunk_count` | `INT` | |
| `language` | `TEXT` | ISO-639-1 |
| `uploaded_at` | `TIMESTAMPTZ` | default `now()` |
| `completed_at` | `TIMESTAMPTZ` | nullable |

Add unique constraint `(user_id, content_hash)` to prevent duplicate uploads per user.

### `chunks`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` PK | |
| `document_id` | `UUID` FK → documents | CASCADE |
| `user_id` | `UUID` FK → users | CASCADE, denormalized for filter performance |
| `chunk_index` | `INT` NOT NULL | 0-based within document |
| `text` | `TEXT` NOT NULL | |
| `page_number` | `INT` | nullable for non-paginated formats |
| `section` | `TEXT` | nullable in MVP |
| `char_offset` | `INT` | start position in normalized text |
| `token_count` | `INT` | approximate |
| `embedding` | `vector(1536)` | nullable until embedded |
| `created_at` | `TIMESTAMPTZ` | default `now()` |

### `conversations`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` PK | |
| `user_id` | `UUID` FK → users | CASCADE |
| `title` | `TEXT` | nullable |
| `created_at` | `TIMESTAMPTZ` | default `now()` |

### `messages`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | `UUID` PK | |
| `conversation_id` | `UUID` FK → conversations | CASCADE |
| `role` | `TEXT` NOT NULL | `user` / `assistant` |
| `content` | `TEXT` NOT NULL | |
| `citations` | `JSONB` | nullable |
| `confidence_score` | `FLOAT` | nullable |
| `created_at` | `TIMESTAMPTZ` | default `now()` |

### Indexes

```sql
CREATE INDEX idx_chunks_embedding_hnsw
  ON chunks USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_chunks_user_doc ON chunks (user_id, document_id);
CREATE INDEX idx_documents_user ON documents (user_id, uploaded_at DESC);
CREATE INDEX idx_messages_conversation ON messages (conversation_id, created_at);
```

**Verification:** `alembic upgrade head` runs cleanly. All tables and indexes exist.
A round-trip insert/select on a 1536-dim vector succeeds.

---

## Step 3 — Authentication

### Endpoints

- `POST /auth/register` — body `{email, password}` → creates user, returns `201`
  - email validated by Pydantic `EmailStr`, lowercased on write
  - password minimum length 8
  - hash with bcrypt (passlib, rounds 12)
  - reject duplicate email with `409`
- `POST /auth/token` — body `{email, password}` → `{access_token, token_type, expires_in}`
  - return `401` on bad credentials without leaking which field was wrong
- `GET /auth/me` — returns `{id, email, created_at}` for the bearer token holder

### JWT

- Algorithm `HS256`, secret from `JWT_SECRET`
- Payload: `{sub: user_id, email, exp, iat}`
- Expiry: `JWT_EXPIRY_SECONDS` (default 3600)
- Refresh tokens are out of scope for Phase 1 — re-login on expiry is acceptable

### FastAPI dependency

Implement `get_current_user(authorization: str = Header(...))` that:

1. Extracts the bearer token
2. Decodes and validates signature + expiry
3. Loads the user row from PostgreSQL
4. Returns the `User` model instance, or raises `401`

All routes except `/auth/*` and `/health` MUST depend on `get_current_user`.

### Row isolation

Every database query that touches `documents`, `chunks`, `conversations`, or `messages`
MUST include `WHERE user_id = :current_user_id`. There are no admin routes in Phase 1.

**Verification:** Two separate users cannot see each other's data through any endpoint.
Write a test that asserts this explicitly.

---

## Step 4 — File Upload Pipeline

### `POST /ingest`
**Auth:** required
**Body:** `multipart/form-data`, field `file`

**Validation:**
- MIME type ∈ `ALLOWED_MIME_TYPES` (PDF / TXT / MD); reject with `415`
- Size ≤ `MAX_UPLOAD_BYTES` (50 MB); reject with `413`
- Compute SHA-256 hash; if `(user_id, content_hash)` already exists, return the
  existing `document_id` with `200` (idempotent re-upload)

**Procedure:**
1. Read file bytes once into memory (acceptable at 50 MB cap)
2. Generate `document_id = uuid4()`
3. Upload to MinIO at `{user_id}/{document_id}/{filename}`
4. Insert `documents` row with `processing_status = 'queued'`
5. Enqueue Celery chain `parse_document.s(document_id) | chunk_document.s() | embed_chunks.s()`
6. Return `201` with `{document_id, filename, processing_status: "queued"}`

### Other document endpoints

- `GET /documents` — list current user's documents, ordered by `uploaded_at DESC`,
  with all status fields. Supports `?status=` filter.
- `GET /documents/{id}` — full document record; `404` if not owned by current user
- `GET /documents/{id}/status` — lightweight `{document_id, processing_status, error_message, chunk_count, completed_at}` for 3-second client polling
- `DELETE /documents/{id}` — hard-deletes the document, all its chunks (via CASCADE),
  and its file in MinIO. Returns `204`.

### MinIO service

Implement `app/services/storage.py` with:

```python
class StorageService:
    async def upload(self, key: str, data: bytes, content_type: str) -> str
    async def download(self, key: str) -> bytes
    async def delete(self, key: str) -> None
    async def exists(self, key: str) -> bool
```

Use `boto3` with `endpoint_url` from `S3_ENDPOINT_URL`.

**Verification:** Uploading the same PDF twice creates only one record. Uploading an
oversized file returns `413`. Uploading a `.zip` returns `415`.

---

## Step 5 — Celery Workers

Celery app config in `app/workers/celery_app.py`:

- Broker: `CELERY_BROKER_URL`
- Result backend: `CELERY_RESULT_BACKEND`
- Task default retry: max 3, backoff `[1, 10, 60]` seconds
- `acks_late = True` (re-deliver if worker dies mid-task)
- Dead-letter exchange for terminally failed tasks

### Worker 1 — `parse_document(document_id)`

1. Load `documents` row; if status not `queued`, abort (idempotency)
2. Set `processing_status = 'parsing'`
3. Download file from MinIO using `storage_path`
4. Branch by `source_type`:
   - **PDF:** `pdfplumber` → list of `{page_num, text}` per page
   - **TXT:** read UTF-8, fall back to `chardet` on `UnicodeDecodeError`
   - **MD:** read raw text (do not strip markdown formatting)
5. Normalize: `ftfy.fix_text()`, collapse runs of whitespace, strip null bytes
6. Detect language with `langdetect`; if not English, set `language` and continue
   anyway (do not block)
7. Persist parsed JSON to MinIO at `{user_id}/{document_id}/parsed.json` to keep the
   `documents` row small
8. Update `word_count`, `language`, `processing_status = 'chunking'`
9. Return `document_id` for the next task in the chain

### Worker 2 — `chunk_document(document_id)`

1. Load parsed JSON from MinIO
2. Use LangChain `RecursiveCharacterTextSplitter`:
   - `chunk_size = 500` (token estimate via `len(text) / 4`)
   - `chunk_overlap = 50`
   - `separators = ["\n\n", "\n", ". ", " ", ""]`
3. For each chunk, derive:
   - `chunk_index` (0-based)
   - `page_number` from the page where the chunk's start offset falls
   - `char_offset` (cumulative position in normalized text)
   - `token_count` (approximate)
   - `section` (left null in MVP — Phase 2 feature)
4. If chunks already exist for this document (idempotency), `DELETE` them first
5. Bulk-insert into `chunks` with `embedding = NULL`
6. Update `chunk_count`, `processing_status = 'embedding'`
7. Return `document_id`

### Worker 3 — `embed_chunks(document_id)`

1. Select chunks for this document where `embedding IS NULL`, ordered by `chunk_index`
2. Batch into groups of 100
3. For each batch:
   - Call OpenAI Embeddings API
   - On `RateLimitError` → retry per Celery retry policy
   - Update each chunk row with its 1536-dim vector
   - Sleep 1 second between batches if document has > 500 chunks
4. When all chunks have embeddings:
   - `processing_status = 'complete'`
   - `completed_at = now()`

### Failure handling

Any unhandled exception in any worker:

- Sets `processing_status = 'failed'`
- Writes truncated stack trace to `error_message` (max 2000 chars)
- Sends event to Sentry
- Pushes the task to the dead-letter queue

**Verification:** Upload a 50-page PDF. Watch all three workers run in order via Celery
logs. Final state: `processing_status = 'complete'`, all chunks have embeddings.

---

## Step 6 — Embedding Pipeline (Service Layer)

Implement `app/services/embedding.py`:

```python
class EmbeddingService:
    async def embed_query(self, text: str) -> list[float]
    async def embed_batch(self, texts: list[str]) -> list[list[float]]
```

- Use the model from `EMBEDDING_MODEL` (default `text-embedding-3-small`)
- Strip and truncate input to 8000 tokens before sending
- Apply tenacity-style retry with exponential backoff on transient errors
- Cache query embeddings in Redis by SHA-256 of normalized text, TTL 24h
- Increment a Prometheus counter `embedding_tokens_total` for cost tracking

**Verification:** `embed_query("hello world")` returns a 1536-element list. Repeated
calls hit the Redis cache.

---

## Step 7 — Semantic Search

### `POST /search`

**Body:**
```json
{
  "query": "how does attention work in transformers",
  "top_k": 5,
  "document_ids": ["uuid1", "uuid2"]
}
```

- `top_k` defaults to `SEARCH_TOP_K_DEFAULT`, capped at 50
- `document_ids` optional; if present, all entries must belong to the current user

**Response:**
```json
{
  "results": [
    {
      "chunk_id": "uuid",
      "document_id": "uuid",
      "document_title": "Attention Is All You Need.pdf",
      "page_number": 3,
      "section": null,
      "text": "An attention function...",
      "similarity_score": 0.91
    }
  ],
  "low_confidence": false,
  "latency_ms": 180
}
```

### Procedure

1. Validate inputs
2. Embed the query (Step 6)
3. Run this query — **always** include `user_id` filter:

```sql
SELECT
  c.id            AS chunk_id,
  c.document_id,
  c.text,
  c.page_number,
  c.section,
  d.filename      AS document_title,
  1 - (c.embedding <=> :query_vec::vector) AS similarity_score
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE c.user_id = :user_id
  AND (:doc_ids::uuid[] IS NULL OR c.document_id = ANY(:doc_ids))
  AND c.embedding IS NOT NULL
ORDER BY c.embedding <=> :query_vec::vector
LIMIT :top_k;
```

4. If max similarity < `SEARCH_LOW_CONFIDENCE_THRESHOLD` (default 0.5),
   set `low_confidence: true` but still return results
5. If zero results, return empty array (do NOT raise)
6. Measure end-to-end latency and include in response

**Verification:** Search latency under 500 ms p95 on a 10k-chunk corpus.
Two users querying the same text receive disjoint result sets.

---

## Step 8 — Q&A Endpoint

### `POST /qa`

**Body:**
```json
{
  "question": "What is the key innovation of the Transformer?",
  "conversation_id": "uuid",
  "top_k": 5,
  "document_ids": ["uuid1"]
}
```

### Procedure

1. Retrieve top-k chunks via Step 7 logic (with `user_id` filter)
2. **No-source guard:** if zero results OR max similarity < `QA_NO_SOURCE_THRESHOLD`
   (default 0.6):
   - Do NOT call the LLM
   - Return:
   ```json
   {
     "answer": "I do not have enough information in my knowledge base to answer this.",
     "citations": [],
     "confidence_score": 0.0,
     "no_source_found": true
   }
   ```
3. Otherwise, build the LLM prompt (template below)
4. Call OpenAI `gpt-4o-mini` with `temperature = LLM_TEMPERATURE` (0.1)
5. Parse `[1]`, `[2]`, … markers from the response. Each marker MUST resolve to a
   chunk index actually included in the prompt — discard unknown markers and log a
   warning.
6. Build the `citations` array from the resolved markers, including
   `document_title`, `page_number`, `section`, `snippet` (first 200 chars of the chunk)
7. `confidence_score` = mean similarity of cited chunks
8. If `conversation_id` is provided, persist the user message and assistant message to
   `messages`. If absent, create a new conversation row first.
9. Return:

```json
{
  "answer": "The key innovation of the Transformer is self-attention [1] ...",
  "citations": [
    {
      "index": 1,
      "chunk_id": "uuid",
      "document_title": "Attention Is All You Need.pdf",
      "page_number": 2,
      "section": null,
      "snippet": "We propose a new simple network architecture..."
    }
  ],
  "confidence_score": 0.87,
  "no_source_found": false
}
```

### LLM Prompt Template

```
You are a citation-grounded research assistant. You answer questions ONLY using the
document excerpts provided below. You must:

1. Cite every factual claim using [1], [2], ... notation matching the excerpt numbers.
2. Never state anything not directly supported by the provided excerpts.
3. If the excerpts do not contain enough information to answer, respond with exactly:
   "I do not have enough information in my knowledge base to answer this."
4. Do not reference your own training knowledge.
5. Be concise and precise.

--- DOCUMENT EXCERPTS ---

[1] Source: {document_title_1}, Page {page_1}{section_clause_1}
{chunk_text_1}

[2] Source: {document_title_2}, Page {page_2}{section_clause_2}
{chunk_text_2}

--- END OF EXCERPTS ---

Question: {user_question}
```

### Prompt-injection mitigation

Wrap each chunk's text in delimiter tokens and instruct the model to treat them as
data, not instructions. Strip control characters from chunk text before assembling.

**Verification:** Asking a question with no relevant documents returns the no-source
fallback WITHOUT calling the LLM (verifiable in logs and cost metrics). Citations
always resolve to chunks belonging to the current user.

---

## Step 9 — Frontend Authentication

Use NextAuth.js v5 with the **Credentials provider** that POSTs to the backend's
`/auth/token` endpoint.

- Pages: `/sign-in`, `/sign-up`
- Session strategy: JWT (NextAuth stores the access token, sets it on every fetch)
- `middleware.ts` redirects unauthenticated traffic away from the `(app)` route group
- `lib/api-client.ts` reads the session token and attaches `Authorization: Bearer <token>`
  to every API request
- On `401` from the backend, the client clears the session and redirects to `/sign-in`

**Verification:** Hitting `/upload` while signed out lands on `/sign-in`. After signing
in, the header dropdown shows the user's email.

---

## Step 10 — Upload UI

Page: `/upload`

Components:

- **DropZone** — accepts PDF / TXT / MD; client-side validates size (50 MB) and MIME
- **UploadList** — current upload session: each item shows filename, size, client-side
  progress bar, then a status badge polling `/documents/{id}/status` every 3 s
- **StatusBadge** — color-coded:
  - `queued` — gray
  - `parsing | chunking | embedding` — amber, with subtle pulse and stage label
  - `complete` — green
  - `failed` — red, with an inline retry button (re-enqueues by re-POSTing the file)

Visual rules:

- Tailwind only, no extra component libraries
- Polished but not flashy — this is an MVP, not a marketing site

**Verification:** Drag-and-drop of a 30-page PDF moves through all four processing
stages live in the UI without manual refresh.

---

## Step 11 — Search UI

Page: `/search`

Components:

- **SearchBar** — debounced 300 ms; submits on Enter or button click
- **FilterPanel** — multi-select of the user's documents (optional scope)
- **ResultCard** — shows:
  - matching snippet with query terms `<mark>`-highlighted client-side
  - document title (clickable, opens library entry)
  - page number, section
  - similarity score badge (`91% match`)
- **EmptyState** — distinct copy for "no documents yet" vs "no results for this query"
- **LowConfidenceBanner** — when API returns `low_confidence: true`

Use TanStack Query (`useSearch`) with `keepPreviousData` so old results stay visible
while a new search loads.

**Verification:** Searching produces results in under 500 ms. Selecting a document
filter restricts results to that document.

---

## Step 12 — Q&A UI

Page: `/qa`

Components:

- **MessageList** — vertical chat thread. User messages right-aligned, assistant
  left-aligned. Auto-scrolls to bottom on new message.
- **MessageInput** — textarea + send button; Enter sends, Shift+Enter newline
- **CitationChip** — inline `[1]`, `[2]` rendered as small pills. Clicking opens a
  popover with `{document_title, page, section, snippet}` and a "View source" link
  to the document detail page
- **ConfidenceBadge** — small subtle badge below assistant messages; only shown when
  `confidence_score >= 0.6`
- **NoSourceMessage** — when `no_source_found: true`, render the assistant message
  in muted italic style with no citations area

Conversation history is local to the session; persisting full history UI to the
backend is deferred. The backend already stores it via Step 8 — surface it in Phase 2.

**Verification:** Asking a question grounded in an uploaded PDF produces an answer
with at least one clickable citation that opens to the correct page.

---

## Step 13 — Error Handling + Observability

### Backend

- `app/core/exceptions.py` — custom exceptions: `NotFoundError`, `PermissionError`,
  `ValidationError`, `ProcessingError`. Map each to an HTTP status via a FastAPI
  exception handler returning `{detail, code, request_id}`.
- structlog JSON-formatted logs to stdout with: `request_id`, `user_id`, `path`,
  `method`, `status_code`, `duration_ms`
- `request_id` middleware: generate UUID per request, propagate to logs and to Celery
  task headers
- `/health` — returns `{status: "ok"}` if the process is alive
- `/readiness` — checks PostgreSQL, Redis, MinIO connectivity; returns `503` if any
  dependency is down
- Sentry init using `SENTRY_DSN_BACKEND`; capture all unhandled exceptions and Celery
  worker failures with `user_id` and `document_id` tagged

### Frontend

- Sentry init using `SENTRY_DSN_FRONTEND`
- Global error boundary in `app/layout.tsx`
- `api-client.ts` surfaces server errors with toast notifications (no silent failures)
- Friendly empty states everywhere — never show a blank screen on error

**Verification:** Killing the postgres container makes `/readiness` return `503` while
`/health` still returns `200`. An uncaught exception in a Celery worker shows up in
Sentry with the full request trace.

---

## Step 14 — Final Integration Testing

Pytest test suite in `backend/tests/`.

### Unit tests

- `test_chunking.py` — chunker produces overlapping chunks of correct size
- `test_embedding.py` — service mocks OpenAI client and verifies cache-hit path
- `test_jwt.py` — token encode/decode + expiry behavior

### Integration tests

Use `pytest-asyncio` and a dedicated test database (Alembic migrations applied per
session).

- `test_auth.py` — register / login / get_me happy paths and error cases
- `test_ingest.py` — upload PDF, poll status, assert chunks exist, assert duplicate
  upload returns the existing record
- `test_search.py` — seed two users, two documents each; assert user A cannot retrieve
  user B's chunks via `/search`
- `test_qa.py`:
  - low-similarity question returns no-source fallback WITHOUT the mocked LLM
    being called
  - normal question with seeded documents returns answer with valid citation indices
  - citation indices that the LLM hallucinates beyond the prompt are dropped silently

### Manual smoke test (end-to-end)

1. `docker compose up`
2. Register two users in the frontend
3. Upload a PDF as user A
4. Confirm processing reaches `complete`
5. Run a search; verify results
6. Run a Q&A; verify citation popover
7. Sign in as user B; confirm A's documents are invisible
8. Run a Q&A as user B with no documents; confirm the no-source fallback fires

---

## Acceptance Criteria

Phase 1 is complete when:

- [ ] `docker compose up` brings up the entire stack with no errors
- [ ] A new user can register, sign in, and sign out
- [ ] A user can upload PDF / TXT / MD files up to 50 MB
- [ ] Processing stages (`queued → parsing → chunking → embedding → complete`) are visible in real time
- [ ] Failed processing surfaces a readable error and a retry path
- [ ] Duplicate uploads (same content hash) return the existing document
- [ ] Semantic search returns ranked results in under 500 ms p95
- [ ] Q&A returns a cited answer for grounded questions
- [ ] Q&A returns the no-source fallback for ungrounded questions WITHOUT calling the LLM
- [ ] All routes except `/auth/*` and `/health` return `401` without a valid token
- [ ] User A cannot read or modify any data belonging to user B through any endpoint
- [ ] `/readiness` returns `503` when any dependency is unhealthy
- [ ] All Pytest tests pass (`pytest backend/tests`)
- [ ] All environment variables are documented in `.env.example`
- [ ] README contains setup, run, and test instructions

---

## Out of Scope for Phase 1

Do NOT implement any of the following — they belong to later phases:

- Knowledge graph, NER, entity extraction, graph visualization
- BM25 keyword search, hybrid RRF fusion, cross-encoder reranking
- OCR for scanned PDFs
- Audio / Whisper transcription
- Web URL crawling, Notion connector, browser extension
- Contradiction detection, source credibility scoring, timeline view
- Personal memory layer, spaced repetition, research assistant mode
- Notes and annotations, collaboration / workspaces
- Automation workflows, semantic alerts, graph export
- Reel / short-form video generation, meme generation
- Streaming LLM responses (SSE)
- WebSocket real-time updates
- Multi-turn conversational memory beyond message persistence
- Cost-routing across multiple LLMs
- Local / on-device embedding models

If a feature is not explicitly listed under Build Steps 1–14, it is out of scope.
