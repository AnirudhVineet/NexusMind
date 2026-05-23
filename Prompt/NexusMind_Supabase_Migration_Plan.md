# NexusMind — Supabase Migration Plan

**Status:** Planning only. No implementation scheduled. Revisit before Phase 2 implementation kickoff.

**Context:** Phase 1 currently runs on local Postgres 16 + pgvector, local filesystem storage, custom JWT auth, and local Redis. This document captures what a migration to Supabase would look like, scoped into reversible phases, so the team can pick a stop-point.

---

## 1. What Supabase Replaces (and What It Doesn't)

| Service | Phase 1 today | Supabase equivalent | Migration weight |
|---|---|---|---|
| Postgres + pgvector | Local Postgres 16 + pgvector + HNSW | Hosted Postgres with pgvector + HNSW (≥ 0.5) | **Low** — env-var swap |
| Auth | Custom JWT (HS256) + `users` + `password_hash` + NextAuth credentials provider | Supabase Auth (GoTrue, RS256/JWKS) + OAuth + magic links | **High** — backend verifier rewrite + frontend NextAuth → `@supabase/ssr` + user-row migration |
| File storage | `./data/files` local FS via `app/services/storage.py` | Supabase Storage (S3-compatible) + signed URLs + bucket policies | **Medium** — service swap + one-time file copy |
| Redis (broker + cache) | Local Redis | **Not provided** — need Upstash / Redis Cloud / self-host | Code unchanged; pick a host |
| Celery workers | Local processes | **Not provided** — Supabase Edge Functions are stateless Deno, not for long jobs | Workers still run wherever you put them |
| FastAPI app | Local | **Not provided** — Supabase doesn't host your Python | Pick Fly.io / Railway / Render / VPS |
| Realtime status updates | Polling `/documents/{id}/status` | Postgres Realtime (websocket subs on `documents.processing_status`) | Optional bonus |
| Row-level security | None | First-class RLS — pays off when workspaces land | Optional bonus |

**Critical:** Supabase replaces your **DB + auth + file store**, not your app server or Redis. You still need a host for FastAPI and Celery (this becomes new decision **D11** in the architecture doc).

---

## 2. Recommended Phased Migration

Each phase is independently shippable and reversible. Stop at any phase that gives enough value.

### Phase A — Database only *(~1 day, low risk, recommended first)*

- Provision Supabase project; enable extensions: `pgvector`, `pgcrypto`.
- Set two connection strings:
  - **Direct** (port 5432) — used by Alembic for migrations.
  - **Pooler** (port 6543, transaction mode) — used by the FastAPI app and Celery workers.
- Run `alembic upgrade head` against the direct URL — schema lands unchanged.
- Migrate existing rows: `pg_dump` from local Postgres → `psql` into Supabase.
- Verify HNSW index recreated and pgvector queries work.

**Untouched:** auth, storage, Redis, Celery, frontend. Reversible by switching `DATABASE_URL` back.

**Wins:** managed backups, point-in-time recovery, dashboard, no Postgres babysitting.

### Phase B — File storage *(~2 days, medium risk)*

- Create a `documents` bucket with per-user path policy: `<user_id>/<document_id>/<filename>`.
- Rewrite `app/services/storage.py` to call `supabase.storage` instead of local FS. Keep the same Python interface so call sites in `parse.py`, `chunk.py`, etc. don't change.
- One-shot migration script copies existing `./data/files/<user>/...` into the bucket.
- Frontend downloads use **signed URLs** issued by the backend — don't proxy bytes through FastAPI.

### Phase C — Auth *(~1 week, high risk; only if you want OAuth / magic links / RLS)*

- **Backend:** replace `app/auth/jwt.py` HS256 verifier with Supabase JWT verification (RS256 + JWKS at `<project>.supabase.co/auth/v1/keys`). `get_current_user()` dependency keeps the same signature; only the verification body changes.
- **Frontend:** drop NextAuth credentials provider; switch to `@supabase/ssr` for cookie-based sessions.
- **User migration:** insert existing rows into `auth.users` via GoTrue admin API. Bcrypt password hashes from Phase 1 import directly if format is compatible (`$2a$`/`$2b$`).
- **RLS policies:** add `USING (auth.uid() = user_id)` on every table. This is a substantial review pass.
- **Cutover risk:** issuing the wrong JWT shape to existing clients will lock everyone out. Stage with a feature flag.

If Phase C feels like too much, **stop after Phase A** (or A+B). Custom JWT keeps working against Supabase Postgres indefinitely.

---

## 3. Things To Flag Before Committing

1. **Free tier auto-pauses after 7 days idle.** Annoying for sporadic personal use; effectively forces Pro ($25/mo) for "always available."
2. **Free tier limits:** 500 MB DB, 1 GB storage, 2 GB egress/mo. pgvector embeddings are large — 768-dim float32 ≈ 3 KB/chunk. 100K chunks ≈ 300 MB just in vectors. Phase 2 adds entity embeddings (`vector(384)`) and relation tables on top. **Plan to be on Pro past a few hundred docs.**
3. **Pooler caveats** (port 6543, transaction mode): breaks `LISTEN/NOTIFY`, server-side prepared statements, and some asyncpg features. SQLAlchemy + asyncpg works if you set `prepared_statement_cache_size=0` and `statement_cache_size=0`. **Alembic must use port 5432 direct**, never the pooler.
4. **Spec posture:** Supabase is metered SaaS, same category as Groq. Already accepted Groq, so Supabase is consistent. The "no paid APIs" rule from the original Phase 2 prompt is now informally relaxed.
5. **Phase 2 LLM data flow doesn't change.** Relation extraction, NER, and intelligence pass all read chunks from Postgres and write back, regardless of where Postgres lives. **Migration order does not have to interleave with Phase 2** — Phase A first, then build Phase 2 on top.
6. **Realtime as a bonus:** replacing the Phase 1 status-polling UI with a Postgres Realtime subscription on `documents.processing_status` is ~50 frontend lines and a nice UX win, but optional and orthogonal to the migration itself.
7. **Backups not on by default on free tier.** Pro tier ships daily backups + 7-day PITR. Turn on before relying on it.
8. **Egress on chunk-heavy responses.** The Graph Explorer and document-intelligence pages pull a lot of bytes; watch the 2 GB free-tier ceiling during demos.

---

## 4. Architecture Doc Deltas (when this lands)

The Phase 2 architecture doc (`NexusMind_Phase2_Architecture.md`) needs these revisions on Supabase migration:

- **D8** — local FS retained → flips to **Supabase Storage** if Phase B ships.
- **D9** — observability unaffected; Supabase dashboard does not replace Prometheus.
- **New D11** — hosting target for FastAPI + Celery. Candidates: Fly.io, Railway, Render, self-managed VPS, Docker on a NAS. Decide before any Supabase work begins, because the FastAPI app needs a public URL Supabase can call back to (for storage signed URLs, webhooks, etc.).
- **Section 5 (Data Model Deltas):** add a one-line note that Alembic migrations target the direct connection (5432) on Supabase, not the pooler.

---

## 5. Recommendation

**Phase A only, before Phase 2 implementation starts.** One-day swap, fully reversible, and gives backups + a managed dashboard while Phase 2 is being built. Defer B and C until there's a concrete trigger:

- Trigger for B: sharing documents publicly, or running on a host without persistent disk.
- Trigger for C: needing OAuth, magic links, multi-device sessions, or starting workspace multi-tenancy work.

If even Phase A feels premature: do nothing. Local Postgres is fine for solo dev, and this plan re-applies whenever you decide to flip the switch.

---

## 6. Open Questions

1. Hosting target for FastAPI + Celery (D11) — needs a separate decision before any Supabase work begins.
2. Redis host — Upstash free tier (10K commands/day) is tight for Celery; Redis Cloud free tier (30 MB) may also pinch. Self-hosted on the same VPS as FastAPI is the cheapest path.
3. Will the project's corpus stay under the Pro tier 8 GB DB limit, or do we need to plan vector storage offload (e.g. Qdrant Cloud, separate pgvector server) at some scale threshold?
4. Is there any compliance/privacy reason corpus data **cannot** leave the local machine? If yes, this whole plan is moot — stay local.

---

*Migration plan for NexusMind, scoped to Supabase. Companion to `NexusMind_Phase2_Architecture.md`. No implementation work is authorized by this document — it is a planning artifact only.*
