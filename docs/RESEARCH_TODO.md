# Research Feature — Improvements TODO

Status: **all 7 tasks implemented (2026-05-23). Verification: ruff clean,
43 research/narration unit tests pass, frontend tsc clean. Postgres-
backed integration tests skipped in dev — re-run with DB up before ship.**

---

## The goal

Make Research "actually useful." Today it generates a JSON brief with
citations baked in, but the UI throws the citations away and the LLM is
asked to synthesize even when the user's library has zero matching
documents — so users see a wall of unverifiable text that may be fully
hallucinated.

## Scope (the 7 things to do)

| # | Task | Status |
|---|---|---|
| 33 | Audit narration button | ✅ Done — diagnosis below |
| 34 | Tighten research prompt + guardrails | ✅ Done |
| 35 | Handle empty-library gracefully | ✅ Done |
| 36 | Replace naive confidence metric | ✅ Done |
| 37 | Render inline citations in UI | ✅ Done |
| 38 | Surface evidence_table + per-doc rollup | ✅ Done |
| 39 | Fix narration button (async refactor) | ✅ Done |

Order to do them in:
1. **Backend service (#34, #35, #36)** — same file, batch together
2. **Backend narration async (#39)** — touches workers/media.py + api/media_narration.py
3. **Frontend UI (#37, #38, plus updates to BriefAudioPlayer)** — depends on backend
4. **Smoke test** — register account, upload doc, ingest it, generate brief, narrate it

---

## Files in scope

```
backend/app/services/research.py            ← #34, #35, #36
backend/app/workers/research.py             ← #35 (just NoEvidenceError handling)
backend/app/workers/media.py                ← #39 (new Celery task)
backend/app/api/media_narration.py          ← #39 (refactor sync→async endpoint)
backend/app/services/media/brief_narration.py ← #39 (already implements the work; will be called from worker)
backend/app/schemas/research.py             ← maybe widen evidence_table shape
frontend/app/(app)/research/page.tsx        ← #37, #38
frontend/components/research/BriefAudioPlayer.tsx ← #39 (poll job status)
frontend/services/narration.ts              ← #39 (return shape will change)
```

---

## Task #34 — Tighten research prompt + guardrails

**File:** `backend/app/services/research.py`

**Why it matters.** Current prompt at `_build_synthesis_prompt` (lines 168–220)
is loose: "Using ONLY the evidence chunks below, produce a comprehensive
research brief." There's no enforcement. The LLM happily emits claims with
no `evidence_chunk_ids` or with IDs that don't exist in the supplied
chunks. We need to validate.

**Concrete changes:**

1. Rewrite the prompt to explicitly forbid uncited claims:
   ```
   RULES (MUST FOLLOW):
   - Every claim in `key_arguments` and `counterarguments` MUST cite at
     least one `chunk_id` from the EVIDENCE CHUNKS section below.
     If you can't cite, omit the claim entirely.
   - Do NOT invent claims, facts, or numbers not present in the evidence.
   - Do NOT reference chunks by paraphrased name — use the exact chunk_id.
   - If the evidence is too sparse to form a coherent argument, set
     `key_arguments` to an empty list and explain in `knowledge_gaps`.
   ```

2. Add post-LLM validation in `synthesize_brief`:
   ```python
   valid_ids = {c["chunk_id"] for c in chunks}
   def _scrub(args):
       out = []
       for arg in args:
           cited = [cid for cid in (arg.get("evidence_chunk_ids") or [])
                    if cid in valid_ids]
           if not cited:
               log.warning("research.dropped_uncited_claim", claim=arg.get("claim", "")[:80])
               continue
           arg["evidence_chunk_ids"] = cited
           out.append(arg)
       return out
   data["key_arguments"] = _scrub(data.get("key_arguments") or [])
   data["counterarguments"] = _scrub(data.get("counterarguments") or [])
   ```

**Done when:** an LLM brief with hallucinated chunk IDs has those claims
silently dropped, and `key_arguments` only contains entries with valid
citations.

---

## Task #35 — Handle empty-library gracefully

**Files:** `backend/app/services/research.py`, `backend/app/workers/research.py`

**Why it matters.** Right now if `gather_evidence` returns 0 chunks (user
has no documents matching the topic), `synthesize_brief` still calls the
LLM with an empty chunks block. The LLM then either (a) hallucinates a
generic brief based on its pretraining, or (b) returns a "minimal fallback
brief" that's a synthesis-failed placeholder. Both presented to the user
as if they were real, sourced briefs. Misleading.

**Concrete changes:**

1. Add `NoEvidenceError(Exception)` at top of `services/research.py`.
2. At the start of `synthesize_brief`, raise it if `len(chunks) == 0`:
   ```python
   if not chunks:
       raise NoEvidenceError(
           "Your library has no documents matching this topic. "
           "Upload relevant material first."
       )
   ```
3. In `workers/research.py::_run_brief`, catch it and set a friendly
   `error_message` instead of letting it become a generic exception:
   ```python
   from app.services.research import NoEvidenceError
   try:
       ...
   except NoEvidenceError as e:
       await _set_status(bid, status="failed", error_message=str(e))
       return   # don't re-raise, no point retrying
   ```
4. Also consider lowering the threshold: if `len(chunks) < 3`, mark as
   failed with "insufficient evidence — only N chunks found, need at least 3."
   (Optional polish — the user can configure.)

**Done when:** generating a brief on a fresh empty library returns a brief
with `status="failed"` and a clear actionable error message in the UI.

---

## Task #36 — Replace naive confidence metric

**File:** `backend/app/services/research.py`

**Current behavior** (line 230):
```python
computed_confidence = min(1.0, unique_doc_count / 5.0)
```
This is always 1.0 if ≥5 docs were sampled. Doesn't reflect retrieval
quality at all.

**New behavior:** weighted average of evidence similarity scores, capped.
```python
import statistics
def _compute_confidence(chunks: list[dict]) -> tuple[float, str]:
    if not chunks:
        return 0.0, "none"
    scores = [float(c.get("score", 0.0)) for c in chunks]
    # Mean of top-10 scores — top-heavy so a few strong chunks count
    top = sorted(scores, reverse=True)[:10]
    mean = statistics.mean(top)
    # Bonus for breadth: more unique docs → slightly higher
    n_docs = len({c["document_id"] for c in chunks})
    breadth_bonus = min(0.1, (n_docs - 1) * 0.02)
    score = min(1.0, mean + breadth_bonus)
    if score < 0.4:
        band = "low"
    elif score < 0.65:
        band = "moderate"
    elif score < 0.85:
        band = "high"
    else:
        band = "very high"
    return score, band
```

Add `evidence_band` to the brief JSON alongside `confidence`. Update the
Pydantic `ResearchBrief` schema in `backend/app/schemas/research.py` to
include `evidence_band: str | None = None` so the API serializer keeps it.

**Done when:** UI can show "Evidence support: high (0.78)" instead of just
a percentage that always rounds to 100%.

---

## Task #37 — Render inline citations in UI

**File:** `frontend/app/(app)/research/page.tsx`

**Current behavior** (lines 88–102): each `key_argument` is rendered as
just `<p>{claim}</p>` + stance badge. The `evidence_chunk_ids` array is
read into the variable but **never displayed**.

**New behavior:** for each argument show its citations inline. Click a
citation → expand to show the chunk's text content and a link to the
source document.

**Implementation outline:**

1. The brief JSON's `evidence_table` already has `chunk_id`, `document_title`,
   `key_point`. Build a `Map<chunk_id, EvidenceItem>` once at the top of
   `BriefDetail`.
2. For each argument, render:
   ```tsx
   <li className="...">
     <p>{arg.claim}</p>
     <div className="flex flex-wrap gap-1 mt-2">
       {arg.evidence_chunk_ids?.map(cid => {
         const ev = evidenceMap.get(cid);
         if (!ev) return null;  // hallucinated chunk_id; should be scrubbed by #34
         return (
           <button onClick={() => setExpandedChunk(cid)}
             className="text-xs px-2 py-0.5 rounded bg-accent/10 hover:bg-accent/20">
             [{ev.document_title?.slice(0,20)}…]
           </button>
         );
       })}
     </div>
     {expandedChunk in arg.evidence_chunk_ids && (
       <blockquote className="mt-2 text-xs italic border-l-2 border-accent/40 pl-3">
         {evidenceMap.get(expandedChunk)?.text || evidenceMap.get(expandedChunk)?.key_point}
         <a href={`/documents/${evidenceMap.get(expandedChunk)?.document_id}`}
            className="text-accent block mt-1">Open document →</a>
       </blockquote>
     )}
   </li>
   ```
3. The `evidence_table` in the brief JSON currently does NOT have `text`
   (full chunk text) or `document_id`. **Two options:**
   - **A. Backend change:** widen `evidence_table` to include `text` and
     `document_id` in `synthesize_brief`. Have the worker build it from
     the retrieved chunks rather than asking the LLM to. Cleaner.
   - **B. Frontend change:** call a new API endpoint to fetch chunk details
     on click. More HTTP traffic, but smaller change.

   **Prefer A.** In `synthesize_brief`, after LLM returns, overwrite
   `data["evidence_table"]` with a deterministic table built from the
   chunks list — same shape but with `text` (first 400 chars) and
   `document_id` filled. This also has the side benefit that the LLM
   can't lie about evidence_table contents.

**Done when:** clicking a citation chip shows the actual chunk text in an
inline quote.

---

## Task #38 — Surface evidence_table + per-doc rollup

**File:** `frontend/app/(app)/research/page.tsx`

After the existing key_arguments / knowledge_gaps / recommended_reading
sections, add two more:

1. **Evidence section** — a collapsible `<details>` listing every chunk
   in `evidence_table`, with chunk text + doc link.

2. **Sources rollup** — a count of unique documents drawn from, with how
   many times each was cited. Helps users see which docs were most
   influential.

   ```tsx
   const sourceCounts = useMemo(() => {
     const counts = new Map<string, { title: string, count: number, doc_id: string }>();
     for (const ev of bj.evidence_table || []) {
       const key = ev.document_id;
       const existing = counts.get(key);
       if (existing) existing.count++;
       else counts.set(key, { title: ev.document_title, count: 1, doc_id: key });
     }
     return Array.from(counts.values()).sort((a, b) => b.count - a.count);
   }, [bj]);
   ```

**Done when:** the user can see which documents fed the brief and how
heavily each was used.

---

## Task #39 — Fix narration button (THE BIG ONE)

**The bug.** `narrate_brief` runs synchronously inside the FastAPI handler
at `backend/app/api/media_narration.py::narrate_brief_endpoint`. For a
5-chapter brief it does ~5 TTS calls (~5–10s each) + ffmpeg concat. Total
30–60s of blocking. The browser usually times out, the user sees
"Internal Server Error", and **the daily narration quota counter was
already incremented** so a second click might 429.

**The fix.** Refactor to a background Celery job. The `BriefNarration`
model already has a `media_job_id` FK column — async was always intended,
just never wired up.

**Steps:**

1. **New Celery task** in `backend/app/workers/media.py`:
   ```python
   @celery_app.task(name="render_brief_narration_job", queue="reel", acks_late=True)
   def render_brief_narration_job(media_job_id: str) -> None:
       """Wraps services.media.brief_narration.narrate_brief in a job."""
       from app.services.media.brief_narration import run_brief_narration_job
       run_async_task(run_brief_narration_job(media_job_id))
   ```

2. **Add `run_brief_narration_job`** in
   `backend/app/services/media/brief_narration.py`. It should:
   - Load the MediaJob row
   - Read params: `brief_id`, `voice_id`, `speed`, `user_id`
   - Set MediaJob status → "rendering" with progress
   - Call the existing `narrate_brief()` (which already works) wrapped in
     try/except
   - On success: write the BriefNarration row, set MediaJob status →
     "complete" with `output_path` pointing at the MP3
   - On failure: refund quota via `decrement_on_failure`, set status →
     "failed" with `error_message`

3. **Refactor the API endpoint** in `backend/app/api/media_narration.py`:
   ```python
   @router.post("/research/briefs/{brief_id}/narrate", status_code=202)
   async def narrate_brief_endpoint(brief_id, payload, user, session):
       # validate brief is complete (existing code)
       # quota check (existing code)
       job = MediaJob(
           user_id=user.id,
           job_type="brief_narration",
           status="queued",
           params={"brief_id": str(brief_id), "voice_id": payload.voice_id, "speed": payload.speed},
       )
       session.add(job); await session.commit(); await session.refresh(job)
       try:
           from app.workers.media import render_brief_narration_job
           render_brief_narration_job.apply_async(args=[str(job.id)], queue="reel", priority=4)
       except Exception:
           decrement_on_failure(str(user.id), "narration")
           raise
       return {"job_id": str(job.id), "status": "queued"}
   ```

4. **Update `frontend/services/narration.ts`**:
   - `narrateBrief()` now returns `{job_id, status}` not `BriefNarration`.
   - Add `getNarrationJob(job_id)` that hits `/api/media/jobs/{id}` (existing endpoint).
   - Keep `getBriefNarration` + `briefNarrationAudioUrl` — they work the
     same after the job completes.

5. **Update `BriefAudioPlayer.tsx`**:
   - On click: call `narrateBrief()`, get back `job_id`, start polling.
   - Show progress bar: "Generating narration… {progress_pct}%".
   - When job status === "complete": fetch the audio blob + render
     `<audio>` like today.
   - On status === "failed": show the error_message clearly.

6. **Don't forget**: the `job_type` "brief_narration" needs to be in the
   list of allowed JOB_TYPES in `backend/app/models/media_job.py` if
   that's enforced anywhere. Check.

**Done when:** clicking 🔊 returns instantly (< 100ms), the UI shows a
"Generating narration… 47%" indicator while NM-media worker chugs, and the
audio appears when ready.

---

## Verification checklist (do all after implementing)

```powershell
# 1. Backend imports cleanly
cd backend
python -c "from app.main import app; from app.workers.celery_app import celery_app; [__import__(m) for m in celery_app.conf.include]; print('ok')"

# 2. Ruff clean
.\.venv\Scripts\ruff.exe check app --select F401,F811,F841 --exclude .venv

# 3. Backend tests
python -m pytest tests/test_research_api.py -q

# 4. Frontend TypeScript clean
cd ..\frontend
npx tsc --noEmit --skipLibCheck

# 5. End-to-end smoke (with servers running):
#    - Sign in
#    - Upload a small PDF, wait for "ready"
#    - Research → topic about the PDF → Generate
#    - Verify citations are clickable + show chunk text
#    - Verify Sources section lists the uploaded PDF
#    - Click 🔊 → should return immediately
#    - Wait ~30s → audio appears
#    - Generate another brief on a topic UNRELATED to anything in library
#      → should fail with "Your library has no documents matching..."
```

---

## Risks / gotchas

1. **The schema change to `evidence_table`** (adding `text` and
   `document_id`) is a breaking change for any existing `brief_json` rows
   in the DB. Old briefs will still render but their evidence_table won't
   have those fields — the frontend should handle `ev.text ?? ev.key_point`.

2. **Streaming was NOT picked** by the user — don't add SSE for synthesis.
   The narration job uses polling on `/api/media/jobs/{id}` which is
   already there.

3. **Voice picker** isn't on the brief page today — narration uses
   whatever's in `UserVoicePreference` (or `null` → first available Piper
   voice). Don't add a voice picker unless explicitly asked; out of scope.

4. **Celery worker restart required** after any worker code change.
   Use `.\scripts\start-worker.ps1` (it kills stale + relaunches).

5. **uvicorn auto-reload** picks up backend/app changes but NOT alembic
   versions. No migration is required for any of these changes — no DB
   schema changes — but verify before declaring done.

---

## Where I left off

All 7 tasks landed (2026-05-23). What changed:

- **#34**: `_build_synthesis_prompt` now has a RULES block forbidding
  uncited claims. `_scrub_arguments` drops any argument whose
  `evidence_chunk_ids` don't match a real chunk.
- **#35**: New `NoEvidenceError`. `synthesize_brief` raises it when
  `chunks` is empty; `workers/research.py::_run_brief` catches it,
  marks the brief failed with the actionable message, returns without
  re-raising (no Celery retry).
- **#36**: `_compute_confidence` returns `(score, band)` from
  `mean(top-10 scores) + breadth_bonus`. `ResearchBrief` schema gained
  `evidence_band: str | None`.
- **#37/#38**: `evidence_table` is now deterministically built from the
  retrieved chunks (with `text`, `document_id`, `score`). Frontend
  renders citation chips inline; clicking expands the quote + source
  link. New Evidence section + Sources rollup with cite counts.
- **#39**: New Celery task `render_brief_narration_job` →
  `services/media/brief_narration.py::run_brief_narration_job`. POST
  `/api/research/briefs/{id}/narrate` now returns 202 + `{job_id, status}`.
  `BriefAudioPlayer` polls `/api/media/jobs/{id}` every 1.5s and shows
  a progress bar until complete. `media_job.JOB_TYPES` gained
  `"brief_narration"`.

Unit tests (`test_research_synthesis.py`) were rewritten to cover the new
confidence formula, `NoEvidenceError`, and `_scrub_arguments`. 43 passing,
4 skipped (Postgres-backed integration tests — run with DB up).

**Worker restart required** to pick up the new Celery task —
`.\scripts\start-worker.ps1`.
