# NexusMind — Phase 4 Prompt for Claude Code

Paste the single prompt below at the start of a new Claude Code session.
It covers orientation, ground rules, and all seven tracks (4.1–4.7) in one
shot. Claude Code will produce a full plan first, wait for your approval,
then implement in dependency order.

Phase 4 is **strictly free**. Every library, model, and service used must be
free of charge within reasonable hobby-tier limits.

---

## Phase 4 Prompt (paste once)

```
You are working on NexusMind — a personal AI knowledge graph system built with
FastAPI + Celery + PostgreSQL/pgvector + Next.js. Phases 1, 2, 2.5, and 3 are
complete. We are starting Phase 4 now, which adds seven tracks:

  A. Personal Memory Layer
  B. Research Assistant Mode
  C+D. Timeline View & Conflict Map UI
  E. Graph Export System
  F. Automation Workflows & Scheduled Ingestion
  G. Semantic Alerts & Notification Center
  H. AI Content Repurposing Engine (free/text edition)

─────────────────────────────────────────────
STEP 1 — ORIENT YOURSELF (do this before anything else)
─────────────────────────────────────────────

Read these files:

1. NexusMind_Phase2_5_Changes.md (root of repo) — the single authoritative
   document covering all deviations from Phases 1 through 3. There is no
   separate Phase3_Changes.md; everything is in this file. Pay attention to:
   - Phase 2.5: no Docker, local filesystem storage, no MinIO/S3, Gemini
     768-dim embeddings, Groq llama-3.3-70b, Ollama qwen2.5 local, mixed
     /api prefix scheme
   - Phase 3: hybrid retrieval + bge-reranker-base, SSE streaming,
     conversation history, multi-source ingestion (URL, OCR, audio,
     YouTube, Notion, ZIP), browser extension, annotations + user_insight
     graph nodes, spaced repetition (SM-2), Prometheus/Grafana dashboards.
     Final Celery queue list: default, ner, intelligence, claims, nli,
     credibility, ocr, transcription, cards (plus dead_letter DLQ)

2. The repo structure. Run `find . -type f -name "*.py" | head -80` and
   `find . -type f -name "*.tsx" | head -80` to get oriented. Read
   backend/app/core/config.py, backend/app/workers/celery_app.py, and
   list all files under backend/alembic/versions/. The current Alembic
   head should be 0014_user_extension_token — confirm this.

There is no NexusMind_Phase4_Plan.md. This prompt is the plan.

After reading, confirm:
1. NexusMind_Phase2_5_Changes.md found and covers through Phase 3
2. Alembic head is 0014
3. Celery queues registered in celery_app.py
4. Contradiction pipeline (claims + nli queues, claim_contradictions table)
   is wired end-to-end
5. Any discrepancy between the changes doc and the actual repo

─────────────────────────────────────────────
STEP 2 — GROUND RULES (non-negotiable for all of Phase 4)
─────────────────────────────────────────────

- ZERO paid services. Allowed API keys: GROQ_API_KEY, GEMINI_API_KEY, a
  personal Notion integration token, or a free Pexels key the user provides.
  NO OpenAI, NO Cohere, NO Sentry (cloud), NO Anthropic API, NO ElevenLabs,
  NO DALL-E, NO AWS, NO Imgflip paid, NO SendGrid paid, NO Resend paid.
  SMTP via Gmail app password is permitted (it's free).
- LLM call order: Groq (free tier) → Ollama (local) as fallback. Never
  call a paid endpoint.
- TTS / image gen / video in Track H: text-only is the MVP. No paid TTS.
  Meme images use Pillow + local CC0 templates only. Video is out of scope.
- NO Docker. Native Windows binaries only. PowerShell scripts to start
  services.
- NO cloud storage. All files go through the existing StorageService
  writing to DATA_DIR. Exports and generated artifacts go under
  DATA_DIR/exports and DATA_DIR/generated.
- 768-dim vectors on the chunk path. The HNSW index is vector(768). Never
  change this dimension on chunks. (Entity embeddings stay at 384-dim
  MiniLM — don't merge the two spaces.)
- Mixed API prefix scheme. New Phase 4 routes go under /api UNLESS
  extending a Phase 1 unprefixed route.
- Single-user-per-account. No workspace_id. Collaboration is out of scope.
- Every new feature gets at least one unit test and a doc section under
  docs/phase4/.
- Source fidelity for Track H: every AI-generated claim must trace back to
  a chunk_id via cosine sim >= 0.75. Flag below-threshold items — don't
  block.

─────────────────────────────────────────────
STEP 3 — WORKING AGREEMENT
─────────────────────────────────────────────

- Before writing any code, produce a single consolidated plan (5–10 bullets
  per track, listing files to create or change). Present it and wait for
  approval.
- When you find a contradiction between this prompt and the actual codebase,
  flag it and ask — don't silently adapt.
- For each Alembic migration, generate the file but DO NOT run it. Print
  the exact `alembic upgrade` command for me to run.
- For each new dependency: pip install, pin in requirements.txt, state the
  version, verify the license is MIT/Apache-2/BSD.
- Run existing tests after every meaningful change. If a previously passing
  test now fails, stop and fix before continuing.
- Don't refactor code outside the current track's scope.
- Implement tracks in this dependency order:
    A (4.1) → B (4.2) → C+D (4.3) → E (4.4) → F (4.5) → G (4.6) → H (4.7)
  E is independent of B–D and can be done in parallel with 4.3/4.4 if
  context allows. H is independent of E–G.

─────────────────────────────────────────────
TRACK A — PERSONAL MEMORY LAYER
─────────────────────────────────────────────

Deliverables:

1. Alembic migration 0015_user_events:
   - Table user_events (id UUID PK, user_id FK, event_type TEXT,
     target_type TEXT, target_id UUID NULLABLE, metadata JSONB DEFAULT '{}',
     created_at TIMESTAMPTZ DEFAULT now())
   - Allowed event_type values: query, qa_answer_viewed, document_viewed,
     chunk_saved, citation_clicked, search_performed, annotation_created,
     card_reviewed
   - Index on (user_id, created_at DESC)
   - Index on (user_id, event_type, created_at DESC)

2. Alembic migration 0016_interest_profile:
   - Table user_interest_profile (user_id PK FK, topic_distribution JSONB,
     last_updated TIMESTAMPTZ, gap_topics JSONB, last_gap_scan TIMESTAMPTZ)
   - JSONB structure: { "topic_name": weight_float } where weights sum to 1.0
   - One row per user, upserted on every recompute

3. Event logging middleware:
   - backend/app/middleware/event_logger.py — FastAPI middleware mapping
     known endpoint paths to event_type values. Write to user_events async
     (background task, don't block the response).
   - Frontend: useLogEvent(eventType, targetId) hook for events the
     middleware can't see (citation_clicked, chunk_saved, document_viewed).
     Calls POST /api/events.
   - Endpoint POST /api/events: accepts { event_type, target_type,
     target_id, metadata }. Reject unknown event_types.

4. Interest profile service (backend/app/services/memory.py):
   - compute_interest_profile(user_id): pull last 90 days of events,
     resolve target_id → topic labels via the document_tags + topic_tags
     join (NOT a topic_tags column — that column doesn't exist on
     chunks/documents). Weighted counts: query=3, view=2,
     citation_click=2, annotation=4, card_review=1, chunk_saved=3.
     Apply exponential time decay (half-life 14 days), normalize to
     sum=1.0, upsert into user_interest_profile.
   - detect_knowledge_gaps(user_id): for each topic in the profile, count
     documents covering it via document_tags. Topics with high weight but
     coverage_count < 3 are gaps. Store top 10 in gap_topics.
   - recommend_documents(user_id, limit=10): find unviewed documents (no
     document_viewed event) ranked by sum(interest_weight * topic_match).
     Exclude docs older than 365 days unless highly matching.
   - Schedule as two Celery beat jobs on a new `memory` queue. Each is a
     SINGLE periodic task that iterates over all active users internally
     (active = ≥1 event in last 7 days). Do NOT create one task instance
     per user:
       - compute_all_interest_profiles: every 6 hours
       - detect_all_knowledge_gaps: once a day

5. Endpoints (all under /api):
   - GET /api/memory/profile
   - GET /api/memory/gaps
   - GET /api/memory/recommendations?limit=10
   - POST /api/memory/refresh (rate-limited: once per minute per user)

6. Worker update: add `memory` queue to scripts/start-worker.ps1.
   Final queue list: default, ner, intelligence, claims, nli, credibility,
   ocr, transcription, cards, memory

7. Frontend: new page /memory with:
   - Interest profile as Recharts bar chart (top 10 topics by weight)
   - "Knowledge Gaps" card grid with topic name, coverage count, link to
     Search filtered by that topic
   - "Recommended for You" list of 10 docs with title, source_type icon,
     topic tags, why-recommended chip
   - "Refresh now" button
   - Small Memory badge widget on the dashboard showing recs + gap counts

8. Tests: test_event_logging.py, test_interest_profile.py,
   test_gap_detection.py, test_recommendations.py

─────────────────────────────────────────────
TRACK B — RESEARCH ASSISTANT MODE
─────────────────────────────────────────────

Deliverables:

1. Alembic migration 0017_research_briefs:
   - Table research_briefs (id UUID PK, user_id FK, topic TEXT, status TEXT,
     brief_json JSONB, exported_paths JSONB DEFAULT '{}', created_at
     TIMESTAMPTZ, completed_at TIMESTAMPTZ NULLABLE, error_message TEXT
     NULLABLE)
   - status values: queued, retrieving, synthesizing, complete, failed

2. Pydantic schemas (backend/app/schemas/research.py):
   - BriefSection(heading: str, content: str, citations: list[str])
   - Argument(claim: str, evidence_chunk_ids: list[str], stance: str)
     (stance: "supporting" | "opposing" | "neutral")
   - ResearchBrief(topic, executive_summary, key_arguments, evidence_table,
     counterarguments, knowledge_gaps, recommended_reading, confidence: float)

3. Service (backend/app/services/research.py):
   - expand_query(topic, n=5): call Groq to generate n sub-questions as a
     JSON array. Parse via Pydantic.
   - gather_evidence(sub_queries, user_id): run Phase 3.1 hybrid_search
     (top 8 per query), deduplicate chunk_ids. Return flat list with
     provenance.
   - synthesize_brief(topic, chunks): call Groq with a strict
     structured-output prompt matching ResearchBrief schema. Require inline
     [chunk_id] citations. Set confidence based on unique-source count,
     cross-source agreement, and whether retrieval sim exceeded
     QA_NO_SOURCE_THRESHOLD. Ollama fallback if Groq fails.

4. Celery: new `research` queue. Task generate_research_brief(brief_id)
   transitions: queued → retrieving → synthesizing → complete|failed.
   Persist status at each step.

5. Endpoints (all under /api):
   - POST /api/research/briefs { topic }
   - GET /api/research/briefs/{id}
   - GET /api/research/briefs (paginated, newest first)
   - GET /api/research/briefs/{id}/export?format=md|pdf|json
     (cache under DATA_DIR/exports/research/{id}.{ext})
   - DELETE /api/research/briefs/{id} (also unlinks exported files)

6. PDF generation:
   - pip install weasyprint (free, LGPL). If WeasyPrint has Windows GTK
     issues, fall back to pip install reportlab.
   - Jinja2 template at backend/app/templates/research_brief.html →
     WeasyPrint → PDF. Template: title page, executive summary, arguments,
     counterarguments, evidence, gaps, reading list, source reference list,
     "Generated by NexusMind" footer with timestamp.
   - Markdown: direct string assembly, no extra dependency.

7. Worker update: add `research` queue to start-worker.ps1.

8. Frontend: new page /research with topic input form, brief list with
   status badges, detail view with collapsible sections + citation chips,
   and Markdown/PDF/JSON export buttons. Poll every 3s while in-progress.

9. Tests: test_query_expansion.py, test_evidence_gather.py,
   test_research_synthesis.py, test_research_export.py,
   test_research_api.py

─────────────────────────────────────────────
TRACK C+D — TIMELINE VIEW & CONFLICT MAP UI
─────────────────────────────────────────────

Note: the contradiction backend (claims + nli queues, claim_contradictions
table) is already fully wired from Phase 2. Confirm edges exist in the DB
before starting. The /conflicts page also already exists from Phase 2.5 —
EXTEND it with resolution UI, do not rewrite it.
BERTopic is already installed (bertopic==0.16.4 in requirements.txt) — do
NOT pip install it again.

Deliverables:

1. Date normalization:
   - pip install dateparser (NOT already installed — check requirements.txt).
   - One-off script backend/scripts/backfill_event_dates.py: for every
     document without event_date, run dateparser on (a) metadata
     captured_at, (b) first 1000 chars of body, (c) URL slug.
   - Migration 0018_event_dates: add event_date DATE NULLABLE to documents
     and chunks (chunks inherit from parent doc). Index both.

2. Chunk-level topic clusters:
   - Migration 0019_chunk_topics: table chunk_topics (chunk_id FK,
     cluster_id INT, cluster_label TEXT).
   - One-off script backend/scripts/build_chunk_topics.py: assign chunk
     cluster membership by joining chunks → documents → document_tags →
     topic_tags (reuse existing BERTopic output; chunks inherit their
     parent document's cluster label). Populate chunk_topics.

3. Timeline endpoints:
   - GET /api/timeline?topic_cluster=X&from=Y&to=Z&entity_id=W
     Returns date-sorted: { id, type, title, date, topic_cluster_id,
     cluster_label, source_type, document_id }
   - GET /api/timeline/clusters — all clusters with labels + counts

4. Conflict resolution endpoints (extend existing /api/contradictions):
   - GET /api/contradictions?topic=X&entity_id=Y&limit=50
   - GET /api/contradictions/{id} (includes 2 surrounding context chunks
     for each claim)
   - PATCH /api/contradictions/{id} { user_resolution }
   - Migration 0020_user_contradiction_state: table linking user_id +
     contradiction_id + state (resolved|dismissed|pending) + note

5. Frontend — new page /timeline:
   - react-chrono (MIT) for timeline, or custom D3 if react-chrono can't
     handle the density.
   - Filter bar: topic cluster multi-select, date range picker, entity
     search, source-type chips.
   - Swim lanes per topic cluster. Each event card is clickable → /library/[id].
   - Right side mini-detail pane for selected event.
   - Empty state when < 5 dated documents.

6. Frontend — extend existing /conflicts page:
   - Add filter sidebar: topic cluster, entity, resolution state, date range.
   - Add three action buttons per card: "A is correct", "B is correct",
     "Not a real conflict" (calls PATCH /api/contradictions/{id}).
   - Dimmed card + resolution badge after resolution.
   - "View evidence" expander showing surrounding context chunks.

7. Graph explorer enhancement: render CONTRADICTS edges with a red dashed
   line + warning icon. Click edge → /conflicts?contradiction_id=...

8. Tests: test_date_backfill.py, test_topic_clusters.py,
   test_timeline_api.py, test_contradictions_api.py

─────────────────────────────────────────────
TRACK E — GRAPH EXPORT SYSTEM
─────────────────────────────────────────────

Note: Phase 2 uses PostgreSQL adjacency tables (entities + entity_edges),
NOT Neo4j. Do not introduce any Neo4j dependency.

Deliverables:

1. Service backend/app/services/graph_export.py:
   - pip install networkx (check requirements.txt first — likely not present).
   - load_subgraph(user_id, filters): query entities + entity_edges from
     PostgreSQL, build networkx.MultiDiGraph. Filters: entity_types,
     min_confidence, topic_cluster_ids, date_range, ego_center_id,
     ego_depth (N-hop ego when set).
   - serialize(graph, format): dispatch to json (node_link_data), csv
     (to_pandas_edgelist + entities CSV zipped), graphml, gexf.
   - Synchronous for < 500 nodes; async Celery task on default queue for
     larger graphs.

2. Migration 0021_graph_exports:
   - Table graph_exports (id UUID PK, user_id FK, format TEXT, filters JSONB,
     file_path TEXT, file_size_bytes BIGINT, status TEXT, created_at
     TIMESTAMPTZ, completed_at TIMESTAMPTZ NULLABLE, expires_at TIMESTAMPTZ
     DEFAULT now() + interval '7 days')
   - Files go under DATA_DIR/exports/graph/{job_id}.{ext}

3. Endpoints (all under /api):
   - POST /api/graph/export { format, filters } → { job_id } (async) or
     stream file (sync). Header X-Export-Mode: sync|async.
   - GET /api/graph/exports/{job_id} — poll status / get download URL
   - GET /api/graph/exports/{job_id}/download — stream file (gzip > 1MB)
   - GET /api/graph/exports — list with timestamps, formats, expiry

4. Cleanup: Celery beat job cleanup_expired_graph_exports runs hourly,
   deletes files + rows where expires_at < now().

5. Frontend: "Export" button in graph explorer toolbar → modal with format
   dropdown, filter section, ego export checkbox + depth slider.
   "Exports" drawer listing recent exports with download + expiry countdown.

6. Tests: test_graph_export_serialize.py, test_graph_export_filters.py,
   test_graph_export_ego.py, test_graph_export_api.py

─────────────────────────────────────────────
TRACK F — AUTOMATION WORKFLOWS & SCHEDULED INGESTION
─────────────────────────────────────────────

Deliverables:

1. Migration 0022_workflows:
   - Table workflows (id UUID PK, user_id FK, name TEXT, trigger_event TEXT,
     conditions JSONB DEFAULT '{}', action_type TEXT, action_config JSONB
     DEFAULT '{}', enabled BOOLEAN DEFAULT true, created_at, last_run_at
     NULLABLE, run_count INT DEFAULT 0)
   - Table workflow_runs (id UUID PK, workflow_id FK, status TEXT,
     triggered_by_event_id UUID NULLABLE, error_message TEXT NULLABLE,
     started_at, completed_at NULLABLE)
   - Table email_settings (user_id PK FK, smtp_host TEXT, smtp_port INT
     DEFAULT 587, smtp_username TEXT, smtp_password_encrypted TEXT,
     from_address TEXT, enabled BOOLEAN DEFAULT false)

2. Migration 0023_feeds:
   - Table rss_feeds (id UUID PK, user_id FK, url TEXT, title TEXT,
     interval_minutes INT DEFAULT 360, last_fetched_at TIMESTAMPTZ NULLABLE,
     last_etag TEXT NULLABLE, last_modified TEXT NULLABLE, enabled BOOLEAN
     DEFAULT true)
   - Table rss_seen_items (feed_id FK, item_guid TEXT, seen_at TIMESTAMPTZ,
     PRIMARY KEY(feed_id, item_guid))

3. Service backend/app/services/workflows.py:
   - Allowed trigger_event values: document_ingested, contradiction_detected,
     semantic_alert_matched, card_due_threshold, brief_generated, gap_detected
   - Allowed action_type values: send_email, fire_webhook, mark_tag,
     create_research_brief, generate_cards, push_notification
   - evaluate_workflows(event_type, event_payload): find enabled matching
     workflows for the user. Apply conditions (topic_in, confidence_gte,
     source_type_in). Enqueue actions as Celery tasks, create workflow_runs.

4. Trigger hooks: wire evaluate_workflows into:
   - End of ingestion pipeline → document_ingested
   - Contradiction detection task → contradiction_detected
   - Card due check beat task → card_due_threshold when due count ≥ threshold
   - Research brief task → brief_generated
   - Gap detection task → gap_detected
   - Stub for semantic_alert_matched (Track G will complete it)

5. Action implementations:
   - send_email: smtplib, reads from email_settings. Fernet-encrypt the
     stored password using JWT_SECRET as the key.
   - fire_webhook: POST to action_config.url, retry 3× with exponential
     backoff. HMAC-SHA256 sign payload with per-workflow auto-generated
     secret.
   - mark_tag: add tag to document in event payload
   - create_research_brief: call Track B service with event's topic
   - generate_cards: call Phase 3.6 task for event's document
   - push_notification: write to notifications table (Track G will deliver)

6. RSS ingestion:
   - pip install feedparser (NOT a Phase 3 dep — install fresh, pin version).
   - Beat job poll_rss_feeds every 5 minutes: find due feeds, enqueue
     fetch_rss_feed(feed_id) on default queue.
   - Worker: feedparser + ETag/Last-Modified conditional fetch. For each new
     item, enqueue ingest_url(item.link) using Phase 3.3 URL task.
     Record item_guid in rss_seen_items to prevent re-ingestion.

7. Endpoints (all under /api): CRUD for /api/workflows, /api/feeds,
   /api/email-settings. Plus POST /api/workflows/{id}/test (synthetic event),
   GET /api/workflows/{id}/runs, POST /api/feeds/{id}/poll-now.

8. Frontend: new page /workflows with three tabs — Rules (wizard),
   Feeds (CRUD), Run History (global runs table). Settings page: Email
   section for SMTP config.

9. Beat config additions: poll_rss_feeds (every 5 min) and
   card_due_threshold_check (daily 8am local time).

10. Tests: test_workflow_eval.py, test_workflow_conditions.py,
    test_workflow_actions.py, test_rss_feed.py, test_webhook_signing.py

─────────────────────────────────────────────
TRACK G — SEMANTIC ALERTS & NOTIFICATION CENTER
─────────────────────────────────────────────

Depends on: Track A (interest profile), Track C+D (contradiction backend),
Track F (workflow trigger emission + email_settings).

Deliverables:

1. Migration 0024_alerts:
   - Table alert_rules (id UUID PK, user_id FK, name TEXT, alert_type TEXT,
     config JSONB, enabled BOOLEAN DEFAULT true, created_at)
     alert_type values: interest_match, contradiction, topic_keyword,
     entity_mention
   - Table notifications (id UUID PK, user_id FK, source_alert_id FK
     NULLABLE, title TEXT, body TEXT, link TEXT, read_at TIMESTAMPTZ
     NULLABLE, dismissed_at TIMESTAMPTZ NULLABLE, created_at, metadata JSONB)
     Index on (user_id, read_at NULLS FIRST, created_at DESC)
   - Table push_subscriptions (user_id FK, endpoint TEXT PK, auth TEXT,
     p256dh TEXT, created_at)

2. Service backend/app/services/alerts.py:
   - check_interest_match(document_id): compute doc embedding (mean of
     chunk embeddings), cosine sim against topic embeddings encoded via
     all-MiniLM-L6-v2. Create notification if max sim ≥ rule threshold
     (default 0.65).
   - check_contradiction(contradiction_id): notify users with interest in
     the affected topic.
   - check_keyword_match(document_id): substring + lemmatized match on
     title and chunks.
   - check_entity_mention(document_id): check if doc mentions watched
     entities.
   - After creating a notification, fire workflow event semantic_alert_matched
     (satisfies the Track F stub).

3. Hooks:
   - End of ingestion pipeline → enqueue run_all_alert_checks(document_id)
     on new `alerts` queue (fans out to the four check_* functions).
   - End of contradiction detection task → enqueue
     check_contradiction(contradiction_id).

4. Notification delivery:
   - In-app: always on (notifications drawer).
   - Browser push: service worker in Next.js app, Web Push API. Generate
     VAPID keys once at first run and store in
     DATA_DIR/config/vapid_keys.json (a simple JSON file — no DB table
     needed for two keys).
   - Email digest: daily beat job per user (default 8am) batching unread
     notifications from last 24h via SMTP from Track F. Skip if no unread.

5. Endpoints (all under /api):
   - CRUD for /api/alerts/rules
   - GET/POST/DELETE for /api/notifications (with read, read-all, dismiss)
   - POST /api/push/subscribe, DELETE /api/push/subscribe/{endpoint_hash}
   - GET /api/push/vapid-public-key

6. Worker update: add `alerts` queue to start-worker.ps1.

7. Frontend: notification bell in global header (unread count badge).
   Notification drawer (slides from right) with mark-read, dismiss,
   click-to-navigate. New page /alerts with three tabs: My Alerts (toggle
   list), Rule Builder (wizard), Settings (push toggle, digest hour,
   test push button). Service worker at frontend/public/sw.js.

8. Tests: test_alerts_interest.py, test_alerts_keyword.py,
   test_alerts_entity.py, test_notifications_api.py,
   test_email_digest.py, test_webpush_keys.py

─────────────────────────────────────────────
TRACK H — AI CONTENT REPURPOSING ENGINE (TEXT EDITION)
─────────────────────────────────────────────

Text-only MVP. NO paid TTS, NO paid image generation, NO video rendering.
Meme images only via Pillow + local CC0 templates. Video is out of scope.

Deliverables:

1. Migration 0025_generated_content:
   - Table generated_content (id UUID PK, user_id FK, source_type TEXT,
     source_id UUID, content_type TEXT, style TEXT, content_json JSONB,
     source_chunks JSONB, fidelity_flags JSONB DEFAULT '[]',
     file_path TEXT NULLABLE, created_at TIMESTAMPTZ,
     edited_at TIMESTAMPTZ NULLABLE)
   - source_type: document | topic | entity | chunk
   - content_type: reel_script | meme | thread | storyboard | caption
   - style: educational | humorous | viral | professional

2. Service backend/app/services/content_engine.py:
   - extract_key_claims(source_chunks, n=8): Groq extractive prompt →
     JSON array of { claim_text, importance: int 1-10, source_chunk_id }.
     Ollama fallback.
   - classify_tone(source_chunks): Groq zero-shot → one of: technical,
     narrative, opinionated, data-heavy. Cache per source.
   - check_source_fidelity(generated_claim, source_chunks): embed claim,
     max cosine sim with source chunk embeddings. Returns
     { pass: bool, max_sim: float, best_source_chunk_id: str }. Threshold
     0.75 default, env var CONTENT_FIDELITY_THRESHOLD overrides.

3. Format generators (all functions in content_engine.py):
   a. generate_reel_script(source_chunks, style) → JSON:
      { hook: { text, duration_seconds, on_screen_text, source_chunk_id },
        beats: [{ text, duration_seconds, visual_direction, on_screen_text,
                  source_chunk_id }],
        cta: { text, duration_seconds },
        caption, hashtags, total_duration_seconds }
      Target 3-5 beats. Visual direction is text description only.

   b. generate_meme(source_chunks, style) → JSON:
      { template_name, top_text, bottom_text, alt_panel_texts,
        caption, source_chunk_id }
      Rendering: Pillow draws text on PNG templates bundled under
      backend/app/assets/meme_templates/. Include 8-12 CC0/public-domain
      templates only. Document source + license in docs/phase4/meme_templates.md.
      Render to DATA_DIR/generated/memes/{id}.png. Font: Impact or Anton
      (Open Font License) if Impact is absent.

   c. generate_thread(source_chunks, style, platform) → JSON:
      { posts: [{ index, text, source_chunk_id, char_count }], total_posts }
      Twitter: max 280 chars, 5-10 posts.
      LinkedIn: max 1300 chars, 3-7 posts.

   d. generate_storyboard(source_chunks, style) → JSON:
      { frames: [{ index, narration, visual, audio_note,
                   duration_seconds, source_chunk_id }] }

   e. generate_caption(source_chunks, platform, style): platform-tuned
      caption (Instagram 2200, LinkedIn 3000, TikTok 2200) + hashtags.

4. Style presets: backend/app/prompts/content_styles/ with educational.txt,
   humorous.txt, viral.txt, professional.txt. Each generator prepends the
   relevant fragment to its prompt.

5. Post-generation fidelity check: run check_source_fidelity on every
   claim-bearing field after generation. Below-threshold items go into
   fidelity_flags. Do not block — surface in UI.

6. Celery: use existing `intelligence` queue (similar to summary tasks).
   All generation is async (LLM calls take 5–30 s).

7. Endpoints (all under /api):
   - POST /api/content/generate
     { source_type, source_id, content_type, style, platform?, strict_mode }
   - GET /api/content/{id}
   - GET /api/content?source_id=&content_type=
   - PATCH /api/content/{id} (re-run fidelity check on edited claims)
   - DELETE /api/content/{id}
   - POST /api/content/{id}/variants?n=3
   - GET /api/content/{id}/export?format=txt|docx|json
   - GET /api/content/{id}/image (meme PNG only)

8. Frontend:
   - "Repurpose" button on /library/[id], entity detail, search results,
     annotation detail.
   - Modal: Step 1 pick content_type, Step 2 style, Step 3 platform
     (thread/caption only), Step 4 strict_mode toggle (raises fidelity
     threshold to 0.85).
   - New page /studio:
     Tab 1 Library: grid with fidelity badge (green/amber/red by flag count).
     Tab 2 Editor: per-format inline editor (beat fields for reel, Canvas
     preview for meme, char counter for thread, frame fields for storyboard).
     Tab 3 Variants: side-by-side comparison, "Copy this one" button.
   - Export: TXT/DOCX/JSON for text formats; "Download PNG" for memes;
     "Copy to clipboard" everywhere.

9. Tests: test_key_claim_extraction.py, test_tone_classification.py,
   test_fidelity_check.py, test_generate_reel.py, test_generate_meme.py,
   test_generate_thread.py, test_content_api.py, test_strict_mode.py

─────────────────────────────────────────────
MIGRATION SEQUENCE
─────────────────────────────────────────────

Current head: 0014_user_extension_token

  0015_user_events                Track A
  0016_interest_profile           Track A
  0017_research_briefs            Track B
  0018_event_dates                Track C+D
  0019_chunk_topics               Track C+D
  0020_user_contradiction_state   Track C+D
  0021_graph_exports              Track E
  0022_workflows                  Track F  (includes email_settings)
  0023_feeds                      Track F
  0024_alerts                     Track G  (includes push_subscriptions)
  0025_generated_content          Track H

─────────────────────────────────────────────
NOW: PRODUCE THE CONSOLIDATED PLAN
─────────────────────────────────────────────

After completing Step 1 (orientation), output a single consolidated plan
covering all seven tracks. For each track list:
- Files to create
- Files to modify
- New dependencies (package + expected license)
- Migration name

Present the plan and wait for my approval before writing any code.
If you find any contradiction between this prompt and the actual codebase
state, call it out in the plan.

Do NOT start coding until I approve the plan.
```

---

## Tips for Working with This Prompt

- Claude Code will produce one large plan covering all seven tracks. Review
  it carefully — the free-only and no-Docker constraints mean wrong defaults
  are hard to unwind.
- After plan approval, Claude Code implements in dependency order (A → B →
  C+D → E → F → G → H). You can pause between any two tracks to review.
- Commit after each track. Tag commits like `phase-4-track-a-complete`.
- Run tests yourself after each track. Don't trust "tests pass" without
  verifying.

### Free-tier limits to watch

- Groq: rate-limited per minute. Track B (research) and Track H (content
  engine) are the heaviest callers. The Ollama fallback must be wired and
  verified before stress-testing.
- Gemini embeddings: generous free cap, but don't re-embed the whole corpus
  in Phase 4. Reuse existing chunk embeddings.
- Gmail SMTP app password: ~500 sends/day. Fine for personal digests.

### If you only have time for the high-impact subset

Skip in this order (Track H + A + B give the most user-facing value):
- Track E (Graph Export) — useful but not a daily driver
- Track F (Automation Workflows) — power-user; RSS ingestion is the most
  useful slice of it
- Track G (Semantic Alerts) — needs notification infra you may not want
- Track C+D (Timeline + Conflict Map) — consumption-only

Minimum viable Phase 4: Tracks A, B, H. That gives personal memory,
research briefs, and content repurposing — which together turn NexusMind
from a research tool into a knowledge-to-output platform.
