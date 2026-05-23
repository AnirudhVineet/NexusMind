# Phase 2 Implementation Prompt — NexusMind Knowledge Graph & Intelligence Layer
### (Free / Self-Hosted Edition)

> **How to use this prompt:** Paste the entire prompt below into your coding assistant (Claude Code, Cursor, Claude.ai, ChatGPT, local LLM, etc.). Optionally attach the NexusMind full spec PDF for additional context. The assistant should respond with a concrete implementation plan, code skeleton, or working code — depending on which mode you select in the "Output Mode" section.

---

## OPERATING CONSTRAINT — ZERO-COST STACK

This entire phase must be implementable with **no paid APIs, no SaaS subscriptions, no metered cloud services**. Every model, library, runtime, and database listed below is open-source / free / self-hostable. The only hard cost is the developer's own machine (CPU + RAM, optionally a GPU). If a deliverable seems to need a paid service, find a local alternative or scope it down — do not silently substitute a paid option.

**Target hardware**: a developer laptop with 16 GB RAM and a 6+ core CPU is the minimum. A 8 GB+ VRAM consumer GPU (e.g., RTX 3060/4060) is strongly recommended for LLM inference; without one, fall back to smaller models (3B class) and accept ~3–5x slower throughput. Document which assumption you're building for.

---

## ROLE & MISSION

You are a senior full-stack AI engineer joining the **NexusMind** project at the start of **Phase 2**. NexusMind is a personal AI knowledge graph system that ingests heterogeneous documents (PDFs, web pages, transcripts, OCR'd images) and exposes them through semantic search, citation-grounded Q&A, an interactive knowledge graph, and AI content repurposing.

Your job in Phase 2 is to **transform the Phase 1 retrieval-only MVP into a knowledge-aware system**: extract entities and relationships, build and visualize a knowledge graph, upgrade retrieval to true hybrid search with reranking, and add document intelligence (multi-level summaries, topic tagging, credibility signals). All using free, self-hosted components.

You must produce **production-conscious work**: typed, tested, observable, and properly integrated with the existing Phase 1 architecture. No greenfield rewrites of Phase 1 code unless explicitly justified.

---

## PHASE 1 BASELINE — WHAT YOU CAN ASSUME EXISTS

Treat the following as already implemented and stable. Do not redesign these layers; integrate with them.

**Backend (FastAPI + Python 3.11+)**
- Async FastAPI app with OpenAPI docs, Pydantic v2 schemas, SQLAlchemy 2.0 (async) ORM, Alembic migrations.
- Celery 5 + Redis worker pool with retry logic and a dead-letter queue.
- JWT auth via NextAuth.js, with `user_id` and `workspace_id` on every authenticated request.

**Data layer (PostgreSQL 16, all self-hosted)**
- Tables: `users`, `workspaces`, `documents`, `chunks`, `embeddings` (with pgvector HNSW index), conversation/citation history.
- Each `chunk` carries: `id`, `document_id`, `page`, `section`, `char_offset`, `heading_context`, `text`, `embedding (vector(768))`.
- Object storage via **self-hosted MinIO** (S3-compatible) keyed by content hash. Run as a Docker container.

**Ingestion pipeline (already wired as a Celery chain)**
- Upload → store raw → parse (PyMuPDF / pdfplumber / Trafilatura, all free) → normalize → chunk (RecursiveCharacterTextSplitter, 512-token windows, 50-token overlap) → embed (**`BAAI/bge-base-en-v1.5` via `sentence-transformers`, 768 dim**, runs locally on CPU or GPU) → index in pgvector HNSW.
- Per-document `processing_status` column tracks pipeline state.

**Retrieval (Phase 1 version)**
- Vector-only similarity search: top-k cosine similarity over pgvector HNSW.
- Single-turn RAG with **a local LLM served via Ollama (default: `qwen2.5:7b-instruct`)**, top-5 chunks, fixed prompt template, basic `[chunk_id]` citation extraction.
- 5-second end-to-end latency target on a CPU-only laptop, 2 seconds with a consumer GPU.

**LLM serving layer**
- **Ollama** running locally on `http://localhost:11434`, exposing the OpenAI-compatible `/v1/chat/completions` endpoint so existing OpenAI-style client code works unchanged.
- Model warm-loaded at boot to avoid cold-start latency on first request.

**Frontend (Next.js 14 App Router + TypeScript + Tailwind)**
- Document upload UI, processing status dashboard, search bar, Q&A pane with citation chips, basic document viewer.
- TanStack Query v5 for server state.

**Observability (all free / self-hosted)**
- Prometheus + Grafana for metrics, **GlitchTip** (self-hosted Sentry alternative) for errors, structured JSON logs via `structlog`. If GlitchTip isn't available, plain Loguru file logging is acceptable.

If any of these assumptions are wrong for your specific repo, ask a clarifying question before generating code.

---

## PHASE 2 DELIVERABLES (in priority order)

Build in this order — earlier deliverables unblock later ones.

### Deliverable 1 — Hybrid Retrieval Upgrade (foundation; do this first)
Reason for priority: every Phase 2 AI feature depends on retrieval quality. Do not build the graph or intelligence features on top of weak retrieval.

- Add **BM25 keyword search** using PostgreSQL `tsvector` / `tsquery` over chunk text. Generate a generated/stored `tsvector` column with a GIN index; weight `heading_context` higher than `text`.
- Implement **Reciprocal Rank Fusion (RRF)** to merge BM25 and vector results (top-50 each → fused list).
- Integrate **`BAAI/bge-reranker-base`** (or `bge-reranker-large` if you have GPU headroom) loaded via `sentence-transformers` `CrossEncoder`. Rerank the fused top-50 down to top-10. Run inference in a Celery worker process so the FastAPI request loop stays unblocked; cache loaded model in worker memory.
- Add **metadata filters** at the SQL level: `source_type`, `author`, `date_range`, `topic_tag`, `document_collection`. Filters apply *before* fusion.
- Cache query results in Redis keyed by `SHA-256(query + filters)` with 5-minute TTL.
- **Acceptance**: on a held-out test set of 50 labeled query→relevant-chunk pairs, hybrid+rerank retrieval improves nDCG@10 by ≥ 15% over the Phase 1 vector-only baseline. Document the eval methodology in `tests/retrieval_eval.py` using the **`ranx`** library (free, fast IR evaluation).

### Deliverable 2 — NER & Entity Extraction Pipeline
- Add a **Celery task `extract_entities(chunk_id)`** that runs after embedding completes for each chunk.
- Use **spaCy `en_core_web_trf`** (transformer-based, free) for built-in entity types (PERSON, ORG, GPE, DATE, EVENT) and **GLiNER** (`urchade/gliner_medium-v2.1`, free, runs on CPU) for custom domain types (CONCEPT, TOOL, METHOD, METRIC). Run them in sequence and merge.
- For each extracted entity, store: `name`, `type`, `canonical_name` (lowercased, stripped, alias-resolved), `entity_embedding` (compute with `sentence-transformers/all-MiniLM-L6-v2`, free, 384 dim), `source_chunk_id`, `char_span`.
- **Entity deduplication / normalization**:
  - On insert, compute cosine similarity between the new entity embedding and existing entities of the same type.
  - If max similarity ≥ **0.92** and string similarity (`rapidfuzz.fuzz.token_sort_ratio`) ≥ 85, merge into the existing entity (append `source_chunk_id` to its evidence list).
  - Otherwise, create a new entity row.
  - Maintain an `entity_aliases` table for the merged surface forms (`ML` → `machine learning`).
- **Acceptance**: on a labeled dedup test set (40 entity pairs, 20 should-merge / 20 should-not), achieve ≥ 90% precision and ≥ 85% recall.

### Deliverable 3 — Relationship Extraction & Graph Storage
- After entity extraction, run an **LLM-based relation extractor** on each chunk: prompt the **local Qwen2.5-7B-Instruct (via Ollama)** with the chunk text and the entity list, asking for typed relations between entity pairs.
- Use Ollama's **structured output mode** (`format` parameter with a JSON schema) to enforce output shape. Qwen2.5 has strong JSON-mode adherence; Llama-3.1-8B is the fallback if Qwen2.5 produces malformed output on your corpus.
- **Allowed relation types** (closed taxonomy — reject anything else): `depends_on`, `contradicts`, `authored_by`, `relates_to`, `is_part_of`, `references`, `co_occurs_with`. Each relation must include a `confidence` score (0–1) and a brief `justification` quote pulled from the chunk.
- **Storage decision**:
  - **MVP path**: PostgreSQL adjacency tables — `entities (id, name, type, canonical_name, embedding, ...)`, `entity_edges (id, src_id, dst_id, relation_type, confidence, evidence_chunk_id, justification)`. Use recursive CTEs for traversal. Choose this if you're under ~50K entities.
  - **Scale path**: **Neo4j Community Edition** (free, single-instance) with the `neo4j-driver` Python client, Cypher for traversal. Wire it as a **second store written in parallel** to PostgreSQL for migration safety. Choose this if you're over ~50K entities or need ≥ 3-hop traversal performance.
  - Pick one and **state the choice explicitly with the criterion that drove it** before writing code.
- **Edge pruning**: drop edges with confidence < 0.7. Run a weekly Celery beat job that re-checks low-confidence edges as new evidence accumulates.
- **Throughput optimization**: batch chunks into groups of 4–8 and send concurrent requests to Ollama (which handles its own request queue). On CPU-only inference, expect ~5–15 chunks/minute; on a 12 GB+ GPU, expect ~60–120 chunks/minute.
- **Acceptance**: on a 5-document seed corpus, the graph contains expected entities and relations verified manually. No orphan nodes (every entity has at least one edge or one source chunk).

### Deliverable 4 — Knowledge Graph Explorer (frontend)
- New page at `/graph` rendering a **force-directed visualization** of the knowledge graph.
- Use **Cytoscape.js** (free, MIT) if rendering > 500 nodes; **D3.js force layout** (free, ISC) if ≤ 500. Decide based on initial graph size and document the choice.
- **Node visuals**: distinct color + icon per type (Concept, Person, Tool, Organization, Event, Date, User-Insight). Node size proportional to evidence count.
- **Edge visuals**: labeled with relation type, weight = confidence. Color edges by relation type.
- **Interactions**:
  - Click node → side panel shows entity name, type, all source chunks with snippets, list of related entities.
  - Double-click node → expand its neighbors up to depth 2 (lazy-loaded via `/api/graph/expand?entity_id=X&depth=2`).
  - Click edge → show the evidence chunk that justified it (with link to the source document at the right page).
  - Type filter (toggle visibility per entity type).
  - Search-within-graph input (filters and centers viewport on matches).
  - Zoom and pan.
- **API**: `GET /api/graph?entity_id=X&depth=N&min_confidence=0.7` returns `{nodes: [...], edges: [...]}` JSON suitable for direct Cytoscape/D3 consumption.
- **Performance**: initial page load returns the top-200 entities by evidence count; the rest is lazy-loaded on user interaction.

### Deliverable 5 — Document Intelligence
For every newly ingested document (and as a backfill batch for existing documents), generate and store the following in a `document_intelligence` JSONB column:

- **Three summary levels**, all generated with the local Qwen2.5 model:
  - `abstract` — single sentence (~25 words) for list views. Use `qwen2.5:7b-instruct`.
  - `summary` — 3–5 bullet executive summary for cards. Use `qwen2.5:7b-instruct`.
  - `deep_dive` — full structured summary with H2 sections detected from the document outline. Use `qwen2.5:14b-instruct` if hardware allows (16 GB+ VRAM); otherwise stay on the 7B model and accept slightly lower quality.
  - Use **map-reduce summarization** for documents over 8K tokens (LangChain `MapReduceDocumentsChain` or hand-rolled — both free).
- **Key insights**: top 5 most information-dense claims as a list of `{claim, source_chunk_id, confidence}`. Use a structured-output LLM prompt (Ollama JSON mode).
- **Topic tags**: 3–7 tags from a hybrid of (a) **BERTopic** (free) unsupervised clustering across the whole corpus (run periodically, not per-document) and (b) LLM zero-shot classification against a small seed taxonomy. Tags become first-class retrieval filters.
- **Reading metrics**: Flesch-Kincaid grade level (`textstat`, free), estimated reading time at 250 wpm, technical jargon density (ratio of words flagged by spaCy NER as technical entities to total content words).
- **Latency budget**: ~30–90 seconds per document for the full intelligence pass on CPU; ~10–25 seconds on GPU. Run as a low-priority Celery queue so it doesn't block user-facing retrieval.

### Deliverable 6 — Source Credibility Scoring (v2 spec only — optional but recommended)
A composite score in `[0, 1]` stored on each `document` row, displayed alongside every citation as a colored badge.

```
credibility_score = w1 * recency_signal
                  + w2 * source_type_signal
                  + w3 * cross_source_agreement
                  + w4 * citation_density
```

- **Recency**: `exp(-age_days / half_life)` with topic-dependent half-life (news = 30 days, peer-reviewed = 730 days).
- **Source type**: lookup table on URL/MIME pattern: peer-reviewed > official docs > established news outlet > independent blog > forum post. (Pure heuristic — no external API needed.)
- **Cross-source agreement**: count of corroborating claims (claim embeddings within 0.85 cosine similarity to claims in other documents). Uses bge-base embeddings already computed.
- **Citation density**: fraction of the document's named entities that already exist in the knowledge graph from other sources.
- Recompute incrementally on every new document ingestion. Expose `GET /api/documents/{id}/credibility` for the UI badge.

### Deliverable 7 — Contradiction Detection (v2 spec only — optional)
- For new chunks, extract atomic claims via the local Qwen2.5 model (`{claim_text, polarity}` list, JSON mode).
- Run a two-stage pipeline:
  - **Stage 1 (cheap filter)**: find candidate contradictory claim pairs by high embedding similarity (≥ 0.85, using bge-base embeddings already computed) AND opposing polarity (one affirmative, one negation; detected via spaCy negation patterns).
  - **Stage 2 (verification)**: run candidates through a **DeBERTa NLI cross-encoder** (`cross-encoder/nli-deberta-v3-base`, free; use `-large` if GPU available) via `sentence-transformers`; keep only pairs classified as `contradiction` with score ≥ 0.8.
- Store as a special `contradicts` edge in the graph with both source chunk IDs as evidence.
- Surface a **Conflict Map** UI: list of detected contradictions, side-by-side claim display with source attribution.

---

## TECH STACK (LOCKED-IN, ALL FREE — do not substitute without justification)

| Concern | Technology | License / Cost |
|---|---|---|
| LLM serving runtime | **Ollama** (local server, OpenAI-compatible API) | MIT / free |
| Primary LLM | **Qwen2.5-7B-Instruct** (`qwen2.5:7b-instruct` in Ollama) | Apache 2.0 / free |
| Larger LLM (if GPU available) | **Qwen2.5-14B-Instruct** | Apache 2.0 / free |
| Fallback LLM | **Llama-3.1-8B-Instruct** (`llama3.1:8b`) | Llama 3 license / free for our use |
| Small/fast LLM (CPU-only) | **Phi-3.5-mini** (`phi3.5:3.8b`) — for low-RAM machines | MIT / free |
| Embeddings | **`BAAI/bge-base-en-v1.5`** (768 dim, via `sentence-transformers`) | MIT / free |
| Embeddings (upgrade) | **`BAAI/bge-large-en-v1.5`** (1024 dim) — better quality, more compute | MIT / free |
| Reranker | **`BAAI/bge-reranker-base`** (cross-encoder) | MIT / free |
| Reranker (upgrade) | **`BAAI/bge-reranker-large`** | MIT / free |
| Entity-similarity embeddings | **`sentence-transformers/all-MiniLM-L6-v2`** (384 dim, fast) | Apache 2.0 / free |
| NER (built-in types) | **spaCy `en_core_web_trf`** | MIT / free |
| NER (custom types) | **GLiNER** (`urchade/gliner_medium-v2.1`) | Apache 2.0 / free |
| Entity dedup | **`rapidfuzz`** (string) + cosine sim on embeddings | MIT / free |
| Topic discovery | **BERTopic** | MIT / free |
| NLI for contradiction | **`cross-encoder/nli-deberta-v3-base`** (or `-large`) | MIT / free |
| Readability | **`textstat`** | MIT / free |
| Date parsing | **`dateparser`** | BSD / free |
| Retrieval evaluation | **`ranx`** | MIT / free |
| Vector storage | **pgvector** extension on PostgreSQL 16 | PostgreSQL license / free |
| Graph storage (default) | **PostgreSQL adjacency tables** | PostgreSQL license / free |
| Graph storage (scale) | **Neo4j Community Edition** | GPLv3 / free for single-instance use |
| Graph viz | **Cytoscape.js** (>500 nodes) or **D3.js** (≤500 nodes) | MIT / ISC / free |
| Object storage | **MinIO** (self-hosted, S3-compatible) | AGPLv3 / free |
| Cache + queue broker | **Redis** (or **Valkey**, BSD-3, if you avoid RSAL) | free either way |
| Job queue | **Celery 5** | BSD-3 / free |
| Error tracking | **GlitchTip** (self-hosted) or Loguru file logs | Apache 2.0 / MIT / free |
| Metrics | **Prometheus + Grafana** | Apache 2.0 / AGPL / free |

**Things deliberately NOT used**: OpenAI API, Anthropic API, Cohere API, Google Gemini API, Pinecone, Weaviate Cloud, Qdrant Cloud, Hugging Face Inference API (paid tiers), AWS Textract, AWS S3 (use MinIO instead), cloud-hosted Sentry. None of these touch the system.

---

## ACCEPTANCE CRITERIA (PHASE 2 IS DONE WHEN…)

1. The hybrid retrieval upgrade beats the Phase 1 baseline on the labeled eval set by ≥ 15% nDCG@10. Eval is reproducible via `pytest tests/retrieval_eval.py` using `ranx`.
2. The NER + dedup pipeline hits ≥ 90% precision and ≥ 85% recall on the labeled dedup test set.
3. The knowledge graph contains zero orphan nodes and zero edges with confidence < 0.7 (after pruning).
4. The `/graph` page loads the top-200-entity initial view in under 2 seconds and remains interactive at 60fps with that node count on a mid-tier laptop.
5. Every document in the corpus has all four document-intelligence fields populated (`abstract`, `summary`, `deep_dive`, tags) and credibility score (if Deliverable 6 included).
6. The full Phase 2 ingestion pipeline (embed → entities → relations → graph → intelligence) processes a 50-page PDF end-to-end in under **15 minutes on CPU-only** or under **5 minutes on a 12 GB+ GPU**, on the existing Celery worker pool.
7. All new code has ≥ 80% test coverage (pytest, with `pytest-asyncio` for async paths).
8. Prometheus metrics exist for: NER task duration, **Ollama tokens/sec and tokens-per-chunk for relation extraction**, graph node/edge growth rate, retrieval latency p50/p95/p99 by retrieval mode (vector-only vs. hybrid vs. hybrid+rerank).
9. Error tracker (GlitchTip or equivalent) captures and groups errors from new background tasks correctly with `user_id` and `document_id` tags.
10. **Zero outbound calls to paid APIs** anywhere in the new pipeline. Add a CI check that greps the codebase for `api.openai.com`, `api.anthropic.com`, `api.cohere.com`, etc. and fails the build if found outside test fixtures.

---

## CONSTRAINTS & GUARDRAILS

- **No regressions in Phase 1.** All existing endpoints (`/search`, `/qa`, upload, status) must continue to work. Add Phase 2 paths alongside, then migrate clients incrementally.
- **Compute budget, not dollar budget.** Relation extraction is the most expensive step on local hardware. Add a per-document **token budget** (default: 50K input tokens to the LLM) checked before kickoff. If the document would exceed the budget, halt and flag for manual chunked re-processing rather than running unbounded.
- **Backpressure on the LLM queue.** Ollama serializes requests internally. If the Celery queue depth for relation-extraction tasks exceeds 100, pause new ingestion and emit a Prometheus alert. Otherwise the system will appear hung.
- **Idempotency.** Every Celery task in the new pipeline must be safely re-runnable. Use `chunk_id` + `task_name` as a deduplication key in a `task_runs` table.
- **Citation integrity.** Every entity, edge, summary, insight, and tag must trace back to at least one `chunk_id`. Add a foreign key constraint; reject records with no evidence.
- **Prompt injection defense.** Document content sent to the LLM must be wrapped in delimited blocks (`<document>…</document>`) with a system instruction to treat it as untrusted data. Sanitize curly-brace template syntax in chunk text before injecting. (Local LLMs are *more* vulnerable than frontier APIs, not less — take this seriously.)
- **Multi-tenant isolation.** Every new query, task, and graph fetch must filter by `workspace_id`. Add a row-level-security policy on every new table.
- **Observability first.** No new background task ships without a Prometheus counter, a duration histogram, and a structured log line at start/success/failure.
- **Model versioning.** Pin Ollama model digests (e.g., `qwen2.5:7b-instruct@sha256:abc123...`) in a `models.lock` file. A model auto-update can break structured-output adherence overnight. Bump versions deliberately, not implicitly.

---

## DEPLOYMENT NOTES

Add to the existing `docker-compose.yml`:

```yaml
services:
  ollama:
    image: ollama/ollama:latest
    ports: ["11434:11434"]
    volumes: ["ollama_data:/root/.ollama"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]   # delete this block if no GPU

  # plus an init container or one-shot script that runs:
  #   ollama pull qwen2.5:7b-instruct
```

The `sentence-transformers`-loaded models (bge-base, bge-reranker, MiniLM, DeBERTa NLI) live inside the Celery worker container — they download on first use to a mounted HuggingFace cache volume so restarts don't re-download.

**First-run model download sizes** (one-time, cached afterward):
- `qwen2.5:7b-instruct` — ~4.7 GB
- `BAAI/bge-base-en-v1.5` — ~440 MB
- `BAAI/bge-reranker-base` — ~1.1 GB
- `sentence-transformers/all-MiniLM-L6-v2` — ~90 MB
- `cross-encoder/nli-deberta-v3-base` — ~750 MB
- `urchade/gliner_medium-v2.1` — ~830 MB
- spaCy `en_core_web_trf` — ~440 MB
- **Total: ~8.5 GB on disk**

Document this in the project README so contributors know what to expect.

---

## OUTPUT MODE (pick ONE before generating)

Tell the assistant which mode you want:

- **Mode A — Architecture & Design.** Produce a detailed Phase 2 architecture document: data model deltas (SQL DDL diffs), API additions (OpenAPI snippets), component diagrams (Mermaid), and a week-by-week implementation plan. No code.
- **Mode B — Code Skeleton.** Produce the full file/folder structure, all module stubs with type signatures and docstrings, SQLAlchemy models, Pydantic schemas, FastAPI route stubs, Celery task stubs, and React component stubs — but no implementation bodies.
- **Mode C — Working Implementation, One Deliverable at a Time.** Pick one of the seven deliverables (specify which), and produce complete, runnable, tested code for it — including migration files, tests, and a short README section explaining how to integrate it.
- **Mode D — Eval Harness Only.** Produce just the retrieval evaluation harness (test queries, scoring functions, baseline runner, `ranx` metrics) so we can measure Phase 1 vs. Phase 2 retrieval before building the rest.

If no mode is specified, default to **Mode A** and ask the user to clarify before producing code.

---

## CLARIFYING QUESTIONS YOU SHOULD ASK BEFORE STARTING

If any of the following are unclear, ask before generating output:

1. Is the existing repo using PostgreSQL adjacency for the graph, or is Neo4j Community already provisioned?
2. What is the size of the current corpus (number of documents and chunks)? This drives the graph storage and viz library choices.
3. **What hardware are we targeting?** CPU-only laptop, consumer GPU (8–12 GB VRAM), or workstation GPU (24 GB+ VRAM)? This drives LLM model selection.
4. Are we already running Ollama, or do we need to add it to the deployment?
5. Are credibility scoring (Deliverable 6) and contradiction detection (Deliverable 7) in scope for this Phase 2 milestone, or deferred to Phase 2.5?
6. Is there a labeled eval set already, or do we need to build one as part of Deliverable 1?
7. Which output mode (A / B / C / D) do you want?

---

## DELIVERABLE FORMAT

Whatever output mode is selected, structure the response as:

1. **TL;DR** — three bullets summarizing what you're producing and why.
2. **Decisions made** — explicit list of architectural choices (e.g., "PostgreSQL adjacency, not Neo4j, because corpus is < 10K entities"; "Qwen2.5-7B over 14B, because target hardware has 8 GB VRAM") with the criterion that drove each.
3. **The deliverable itself** — design doc, code, or eval harness as appropriate.
4. **What this does NOT cover** — explicit list of Phase 2 work still pending after this output.
5. **Next concrete step** — the single next action to take.

---

*End of Phase 2 implementation prompt — Free / Self-Hosted edition. Generated for NexusMind (a.k.a. NexusMind) project, derived from v1.0 and v2.0 specifications.*
