# Phase 5 — Celery queue inventory + priorities

Phase 5 adds a single new queue: **`reel`**. All Phase 5 media tasks
(reel render, narration, storyboard, bundle export) run on it.

To avoid head-of-line blocking — a 90 s reel render shouldn't block a
2 s narration — tasks are enqueued with explicit priorities:

| Task | Queue | Priority |
|---|---|---|
| `render_narration_job` | reel | **5** (highest) |
| `render_storyboard_job` | reel | 4 |
| `render_reel_job` | reel | 3 |
| `render_bundle_export_job` | reel | 2 |

Lower numbers mean Celery executes the task sooner. Priorities only apply
within a single queue; cross-queue ordering is unchanged.

The `reel` queue is consumed by a dedicated worker process
(`NM-media`, defined in `scripts/start-worker.ps1`) with
`REEL_WORKER_CONCURRENCY=2` slots by default. Bumping concurrency above 2
typically requires more CPU than a single machine has spare during a
reel render.

## Full queue inventory (after Phase 5)

```
default       ← parse, chunk, embed (Phase 1 + 3.3)
ner           ← entity extraction
relations     ← relation extraction (Ollama)
intelligence  ← summarization, BERTopic
maintenance   ← prune + recompute
claims        ← claim extraction
nli           ← contradiction detection
credibility   ← credibility scoring
ocr           ← scanned PDF OCR
transcription ← audio transcription
cards         ← spaced repetition card generation
memory        ← Phase 4 interest profile + gaps
research      ← Phase 4 brief synthesis
alerts        ← Phase 4 semantic alerts
reel          ← Phase 5 reel/narration/storyboard/bundle render
dead_letter   ← permanent failures
```
