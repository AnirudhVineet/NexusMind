"""Centralised Prometheus metric registry for Phase 2.

Import metrics from here in workers and API code rather than defining them
inline, so the registry stays single-source-of-truth and labels are consistent.
"""
from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


# Use the process-default registry. Each Celery worker process gets its own
# registry — that's fine for /metrics scraping since FastAPI exposes its own.
NER_DURATION = Histogram(
    "nexusmind_ner_duration_seconds",
    "Time spent in NER extraction per chunk, by extractor.",
    labelnames=("extractor",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)

OLLAMA_TOKENS_PER_SECOND = Histogram(
    "nexusmind_ollama_tokens_per_second",
    "Ollama generation throughput, by task type.",
    labelnames=("task",),
    buckets=(5, 10, 20, 40, 80, 160, 320),
)

OLLAMA_TOKENS_PER_CHUNK = Histogram(
    "nexusmind_ollama_tokens_per_chunk",
    "Ollama tokens consumed per chunk, by task type.",
    labelnames=("task",),
    buckets=(50, 100, 250, 500, 1000, 2500, 5000, 10000),
)

GRAPH_ENTITIES_TOTAL = Gauge(
    "nexusmind_graph_entities_total",
    "Total entities currently stored across all users.",
)

GRAPH_EDGES_TOTAL = Gauge(
    "nexusmind_graph_edges_total",
    "Total entity edges currently stored, by relation type.",
    labelnames=("relation_type",),
)

CELERY_QUEUE_DEPTH = Gauge(
    "nexusmind_celery_queue_depth",
    "Pending tasks per Celery queue.",
    labelnames=("queue",),
)

INGEST_PAUSED = Counter(
    "nexusmind_ingest_paused",
    "Count of ingestion-pause events emitted, by reason.",
    labelnames=("reason",),
)

TASK_FAILURES = Counter(
    "nexusmind_task_failures_total",
    "Count of failed Phase 2 background tasks, by task name.",
    labelnames=("task",),
)

# ---- Phase 2.5 metrics -------------------------------------------------------

CLAIMS_EXTRACTED = Counter(
    "nexusmind_claims_extracted_total",
    "Atomic claims successfully extracted and stored, by polarity.",
    labelnames=("polarity",),
)

CLAIMS_PER_CHUNK = Histogram(
    "nexusmind_claims_per_chunk",
    "Number of claims extracted per chunk.",
    buckets=(0, 1, 2, 3, 5, 8, 13, 20),
)

CONTRADICTION_STAGE1_CANDIDATES = Histogram(
    "nexusmind_contradiction_stage1_candidates",
    "Candidate pairs surfaced by the pre-filter stage per claim.",
    buckets=(0, 1, 2, 3, 5, 10, 20),
)

NLI_DURATION = Histogram(
    "nexusmind_nli_duration_seconds",
    "DeBERTa NLI inference time, bucketed by batch size.",
    labelnames=("batch_size_bucket",),
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
)

CONTRADICTIONS_TOTAL = Counter(
    "nexusmind_contradictions_confirmed_total",
    "Contradiction outcomes, by disposition.",
    labelnames=("outcome",),
)

CREDIBILITY_COMPUTE_DURATION = Histogram(
    "nexusmind_credibility_compute_seconds",
    "Time to compute a credibility score.",
    labelnames=("kind",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

CREDIBILITY_COHORT_SIZE = Histogram(
    "nexusmind_credibility_cohort_size",
    "Number of neighbor documents re-scored per fan-out.",
    buckets=(0, 1, 2, 5, 10, 20, 50, 100),
)

CREDIBILITY_SCORE = Histogram(
    "nexusmind_credibility_score",
    "Distribution of credibility scores written (sampled on compute).",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)

SOURCE_TYPE_MATCH = Counter(
    "nexusmind_source_type_match_total",
    "Source-type signal matches, by matched label.",
    labelnames=("source_label",),
)


# ---- Phase 3.1 metrics -------------------------------------------------------

RETRIEVAL_DURATION = Histogram(
    "nexusmind_retrieval_duration_seconds",
    "Retrieval stage latency.",
    labelnames=("stage",),  # vector | bm25 | rrf | rerank | total
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 4, 8),
)

RETRIEVAL_CACHE_HITS = Counter(
    "nexusmind_retrieval_cache_hits_total",
    "Search result cache hits.",
)

RETRIEVAL_CACHE_MISSES = Counter(
    "nexusmind_retrieval_cache_misses_total",
    "Search result cache misses.",
)

LLM_TOKENS_TOTAL = Counter(
    "nexusmind_llm_tokens_total",
    "LLM tokens consumed.",
    labelnames=("provider", "model", "direction"),  # direction: prompt | completion
)

LLM_REQUESTS_TOTAL = Counter(
    "nexusmind_llm_requests_total",
    "LLM API requests.",
    labelnames=("provider", "model"),
)

LLM_DURATION = Histogram(
    "nexusmind_llm_duration_seconds",
    "LLM API call latency.",
    labelnames=("provider", "model"),
    buckets=(0.5, 1, 2, 4, 8, 15, 30, 60),
)

INGESTION_STATUS = Counter(
    "nexusmind_ingestion_status_total",
    "Ingestion pipeline events.",
    labelnames=("source_type", "status"),  # status: queued | complete | failed
)

__all__ = [
    "NER_DURATION",
    "OLLAMA_TOKENS_PER_SECOND",
    "OLLAMA_TOKENS_PER_CHUNK",
    "GRAPH_ENTITIES_TOTAL",
    "GRAPH_EDGES_TOTAL",
    "CELERY_QUEUE_DEPTH",
    "INGEST_PAUSED",
    "TASK_FAILURES",
    # Phase 2.5
    "CLAIMS_EXTRACTED",
    "CLAIMS_PER_CHUNK",
    "CONTRADICTION_STAGE1_CANDIDATES",
    "NLI_DURATION",
    "CONTRADICTIONS_TOTAL",
    "CREDIBILITY_COMPUTE_DURATION",
    "CREDIBILITY_COHORT_SIZE",
    "CREDIBILITY_SCORE",
    "SOURCE_TYPE_MATCH",
    # Phase 3.1
    "RETRIEVAL_DURATION",
    "RETRIEVAL_CACHE_HITS",
    "RETRIEVAL_CACHE_MISSES",
    "LLM_TOKENS_TOTAL",
    "LLM_REQUESTS_TOTAL",
    "LLM_DURATION",
    "INGESTION_STATUS",
    # Phase 5 — Media pipeline
    "MEDIA_JOBS_TOTAL",
    "MEDIA_JOB_DURATION",
    "MEDIA_COST_USD_TOTAL",
    "VISUAL_PROVIDER_CALLS",
    "TTS_PROVIDER_CALLS",
    "MEDIA_DISK_USED_BYTES",
]

# ─── Phase 5 metrics ────────────────────────────────────────────────────────

MEDIA_JOBS_TOTAL = Counter(
    "nexusmind_media_jobs_total",
    "Total media render jobs by type and final status.",
    labelnames=("job_type", "status"),
)

MEDIA_JOB_DURATION = Histogram(
    "nexusmind_media_job_duration_seconds",
    "Wall-clock duration of a media render job.",
    labelnames=("job_type",),
    buckets=(5, 10, 30, 60, 120, 300, 600, 1800),
)

MEDIA_COST_USD_TOTAL = Counter(
    "nexusmind_media_cost_usd_total",
    "Cumulative estimated USD spend by provider.",
    labelnames=("provider",),
)

VISUAL_PROVIDER_CALLS = Counter(
    "nexusmind_visual_provider_calls_total",
    "Visual-provider invocations, by provider and outcome.",
    labelnames=("provider", "status"),
)

TTS_PROVIDER_CALLS = Counter(
    "nexusmind_tts_provider_calls_total",
    "TTS-provider invocations, by provider and outcome.",
    labelnames=("provider", "status"),
)

MEDIA_DISK_USED_BYTES = Gauge(
    "nexusmind_media_disk_used_bytes",
    "Per-user media disk usage.",
    labelnames=("user_id",),
)
