# NexusMind — Performance Improvement Plan

**Status:** Planning only. No implementation scheduled.
**Companion to:** `NexusMind_Phase2_Architecture.md`, `NexusMind_Supabase_Migration_Plan.md`.

---

## 0. Framing

**"The website is slow" is not actionable until it's measured.** The fix for slow first-paint is different from slow Q&A is different from slow upload-status. The first concrete step in this plan is *measurement*, not optimization. Every later item should be re-prioritized after real numbers exist.

This plan ranks likely culprits in the existing Phase 1 stack (FastAPI + SQLAlchemy async, Next.js 14 App Router, TanStack Query, pgvector HNSW, Groq LLM, Gemini embeddings, local FS), with rough effort and expected impact for each.

---

## 1. Step 0 — Measure (do this first, ~1 hour)

Cannot be skipped. Without baseline numbers, every later item is a guess.

- **Browser DevTools** on each slow page: Network tab (TTFB, total requests, slowest single request) and Performance tab (main-thread blocking, layout/paint).
- **Backend** — add a one-line middleware that logs `{method} {path} {status} {duration_ms}` for every API call. After clicking through the slow flows, the slowest endpoint by p95 names itself.
- **Postgres** — set `log_min_duration_statement = 200` for a day. Any query > 200 ms shows up in the log.
- **Pick one offender** — the single worst p95-latency endpoint or query. Fix that first. Re-measure. Repeat. Don't optimize what hasn't been measured.

---

## 2. Likely Culprits (Ranked by Expected Impact)

### 2.1 Query embedding round-trip on every Q&A — biggest hidden tax
Every `/qa` call hits Google Gemini's embedding API over the network to embed the question (~300–500 ms) **before** retrieval starts. Likely 30–50% of total Q&A latency.

- **Fix:** swap query-time embedding to a local model (`bge-base-en-v1.5` via `sentence-transformers`, warm-loaded in the FastAPI process). 5 ms instead of 400 ms.
- **Bonus:** aligns with Phase 2's planned switch to bge-base for new chunk embeddings — same model for query and corpus is correct.
- **Effort:** half day. **Impact:** very high.

### 2.2 `get_current_user()` queries Postgres on every authed request
JWT decode is followed by a `SELECT * FROM users WHERE id = …` on every authenticated call.

- **Fix:** cache the user row in Redis keyed by `user_id`, TTL 5 min. Or trust the JWT claims (`sub`, `email`) on hot paths and skip the DB lookup entirely.
- **Effort:** 1 hour. **Impact:** medium — saves ~10–30 ms per request, but every request.

### 2.3 TanStack Query default `staleTime: 0` + no prefetching
Every page navigation refetches data that was just shown. Library list, document detail, conversation history all re-hit the API on each visit.

- **Fix:** set per-query `staleTime` — e.g. `60_000` for the library list, `Infinity` for static lookups, shorter for live status. Use `prefetchQuery` on hover/route-change for predictable navigations (library row → document detail).
- **Effort:** 2 hours. **Impact:** high on *perceived* speed (instant navigation).

### 2.4 Document status polling
Upload page almost certainly polls `/documents/{id}/status` on a fixed short interval. With long ingests or multiple tabs open, that compounds into a lot of wasted requests.

- **Fix:** exponential backoff (1 s → 2 s → 4 s → 8 s, cap at 10 s) and pause polling when `document.visibilityState !== 'visible'`. Real fix is Postgres Realtime / SSE, but backoff alone halves the load and is 1-hour work.
- **Effort:** 1 hour. **Impact:** medium.

### 2.5 HNSW `ef_search` not tuned
pgvector default is `ef_search = 40`. For the current corpus size that may be over- or under-provisioned. Lowering trades a tiny bit of recall for ~2× faster vector search.

- **Fix:** `SET LOCAL hnsw.ef_search = 20;` at the start of the retrieval transaction; benchmark recall on the Phase 2 eval set.
- **Effort:** 1 hour (gated on eval set existing — Phase 2 week 1). **Impact:** low–medium.

### 2.6 Frontend bundle / first paint
Next.js App Router defaults are good, but a single accidentally-imported heavy lib (markdown renderer, syntax highlighter, charting) at the top level can blow up the initial client chunk.

- **Fix:** run `npx @next/bundle-analyzer`. Anything > 100 KB in a critical client chunk → `next/dynamic` with `ssr: false`. Audit `app/(app)/qa/page.tsx` first — it likely imports a markdown/syntax stack.
- **Effort:** half day. **Impact:** depends entirely on what the analyzer shows.

### 2.7 No HTTP caching headers
Read-mostly responses (document metadata, citation lists, conversation lists) likely don't set `Cache-Control`. Browser refetches each time.

- **Fix:** add `Cache-Control: private, max-age=60` on read-only endpoints that change infrequently. Use `ETag` for endpoints where freshness matters more.
- **Effort:** 1 hour. **Impact:** low–medium.

### 2.8 Database connection pool size
SQLAlchemy default `pool_size=5` serializes requests under any concurrency.

- **Fix:** `pool_size=20, max_overflow=10` on the async engine. Watch Postgres `max_connections` (default 100) so it isn't exhausted by Celery workers + FastAPI together.
- **Effort:** 5 minutes. **Impact:** low for solo use, high under concurrency.

---

## 3. Quick-Wins-vs-Structural Map

| Bucket | Items | Total effort | Expected outcome |
|---|---|---|---|
| **Quick wins (this week)** | 2.1 query embedding swap, 2.3 TanStack staleTime, 2.4 polling backoff, 2.8 pool size | ~1.5 days | Q&A latency roughly halves; navigation feels instant; load drops |
| **Cleanup (next week)** | 2.2 user caching, 2.7 cache headers, 2.6 bundle audit | ~1 day | Backend p95 down 10–30 ms across the board; first-paint trim |
| **Structural (Phase 2 / 2.5)** | 2.5 HNSW tuning (gated on eval), Realtime status (Supabase Phase A unlock), Phase 2 retrieval cache (Redis) | Already in Phase 2 plan | Compound gains as those features land |

---

## 4. Items That Already Land in Phase 2

These are not separate work — they're already in `NexusMind_Phase2_Architecture.md` and will improve perceived speed when shipped:

- **Redis result cache** on `/search/v2` (5 min TTL, key = `SHA-256(query + filters)`) — repeat queries become free.
- **Embedding model switch to bge-base** — fixes 2.1 as a side effect.
- **Reranker stage** — slightly *increases* per-query latency (~50–150 ms for top-50 → top-10) but improves answer quality enough that users issue fewer follow-up queries. Net latency-per-task often improves.
- **Prometheus histograms** for retrieval p50/p95/p99 by mode — gives the missing observability for ongoing tuning.

---

## 5. What This Plan Does NOT Cover

- **Mobile / responsive performance.** Desktop-first; mobile is Phase 3.
- **Cold-start latency on serverless hosting.** Only relevant once D11 (hosting target) is decided. Fly.io / Railway / VPS-style hosts don't have this; truly serverless does.
- **CDN / edge caching of static assets.** Next.js handles most of this at build time; revisit only if first-paint TTFB is the named bottleneck after measurement.
- **LLM streaming.** The Q&A endpoint likely returns the full answer at once; streaming the response (SSE) wouldn't reduce total latency but would massively improve perceived speed. Worth doing — captured here as a Phase 2.5 ticket rather than this plan.
- **Image optimization.** No image-heavy flows in Phase 1.
- **Worker → DB write batching.** Embed/chunk write paths could batch better, but that's pipeline throughput, not user-facing latency.

---

## 6. Recommended Sequence

1. **Today (1 hour):** add the request-duration middleware to FastAPI, set `log_min_duration_statement = 200` on Postgres, click through the slow flows, **collect numbers**.
2. **This week (half day):** §2.1 — swap query embedding to local bge-base. Single biggest expected win, on the Phase 2 path anyway.
3. **This week (2 hours):** §2.3 — tune TanStack Query `staleTime` + prefetch on the library page.
4. **This week (1 hour):** §2.4 — status-polling exponential backoff + visibility-aware pause.
5. **Re-measure.** The new logs will name the next target. Do not pre-commit to §§2.5–2.8 before this re-measurement — priorities will likely shift.

---

## 7. Open Question

**Which symptom hurts most right now?** This routes effort to the right culprit:

- Slow **Q&A response** → §2.1 (query embedding) + later LLM streaming.
- Slow **page navigation** → §2.3 (TanStack staleTime + prefetch).
- Slow **upload/status updates** → §2.4 (polling backoff) + Realtime later.
- Slow **first page load** → §2.6 (bundle audit) + §2.7 (cache headers).
- Slow **search itself (after query is sent)** → §2.5 (HNSW) + Phase 2 RRF/rerank cache.

Pick one and the order above changes; the other items still apply but slip in priority.

---

*Performance plan for NexusMind, scoped to user-facing latency. Companion to the Phase 2 and Supabase docs. No implementation work is authorized by this document — it is a planning artifact only.*
