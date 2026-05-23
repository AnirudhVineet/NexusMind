from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the .env file relative to this config file's location
# config.py is at app/core/config.py — parents[3] reaches the project root
_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Database
    database_url: str = Field(alias="DATABASE_URL")
    database_sync_url: str = Field(alias="DATABASE_SYNC_URL")

    # Cache + broker
    redis_url: str = Field(alias="REDIS_URL")
    celery_broker_url: str = Field(alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(alias="CELERY_RESULT_BACKEND")

    # Object storage (local filesystem)
    storage_dir: str = Field(alias="STORAGE_DIR", default="./data/files")

    # AI: LLM (Groq, OpenAI-compatible — Phase 1 default)
    groq_api_key: str = Field(alias="GROQ_API_KEY")
    groq_base_url: str = Field(
        alias="GROQ_BASE_URL", default="https://api.groq.com/openai/v1"
    )
    llm_model: str = Field(alias="LLM_MODEL", default="llama-3.3-70b-versatile")
    llm_temperature: float = Field(alias="LLM_TEMPERATURE", default=0.1)

    # AI: Local LLM (Ollama, OpenAI-compatible — Phase 2 onwards)
    llm_provider: str = Field(alias="LLM_PROVIDER", default="groq")  # "groq" | "ollama"
    ollama_base_url: str = Field(
        alias="OLLAMA_BASE_URL", default="http://localhost:11434/v1"
    )
    ollama_model_primary: str = Field(
        alias="OLLAMA_MODEL_PRIMARY", default="qwen2.5:7b-instruct"
    )
    ollama_model_fallback: str = Field(
        alias="OLLAMA_MODEL_FALLBACK", default="llama3.1:8b"
    )
    ollama_json_mode_timeout_s: int = Field(
        alias="OLLAMA_JSON_MODE_TIMEOUT_S", default=60
    )
    models_lock_path: str = Field(alias="MODELS_LOCK_PATH", default="models.lock")

    # AI: Embeddings (Google Gemini)
    gemini_api_key: str = Field(alias="GEMINI_API_KEY")
    embedding_model: str = Field(alias="EMBEDDING_MODEL", default="text-embedding-004")
    embedding_dim: int = Field(alias="EMBEDDING_DIM", default=768)

    # Retrieval
    search_top_k_default: int = Field(alias="SEARCH_TOP_K_DEFAULT", default=5)
    qa_no_source_threshold: float = Field(alias="QA_NO_SOURCE_THRESHOLD", default=0.6)
    search_low_confidence_threshold: float = Field(alias="SEARCH_LOW_CONFIDENCE_THRESHOLD", default=0.5)

    # Auth
    jwt_secret: str = Field(alias="JWT_SECRET")
    jwt_algorithm: str = Field(alias="JWT_ALGORITHM", default="HS256")
    jwt_expiry_seconds: int = Field(alias="JWT_EXPIRY_SECONDS", default=3600)

    # Limits
    max_upload_bytes: int = Field(alias="MAX_UPLOAD_BYTES", default=52_428_800)
    allowed_mime_types_csv: str = Field(
        alias="ALLOWED_MIME_TYPES",
        default="application/pdf,text/plain,text/markdown",
    )

    @property
    def allowed_mime_types(self) -> List[str]:
        return [m.strip() for m in self.allowed_mime_types_csv.split(",") if m.strip()]

    # Phase 2 NER pipeline
    entity_dedup_cosine_threshold: float = Field(
        alias="ENTITY_DEDUP_COSINE_THRESHOLD", default=0.92
    )
    entity_dedup_fuzz_threshold: int = Field(
        alias="ENTITY_DEDUP_FUZZ_THRESHOLD", default=85
    )
    entity_embedding_model: str = Field(
        alias="ENTITY_EMBEDDING_MODEL", default="sentence-transformers/all-MiniLM-L6-v2"
    )
    spacy_model: str = Field(alias="SPACY_MODEL", default="en_core_web_trf")
    gliner_model: str = Field(
        alias="GLINER_MODEL", default="urchade/gliner_medium-v2.1"
    )
    gliner_labels_csv: str = Field(
        alias="GLINER_LABELS",
        default="concept,tool,method,metric",
    )

    @property
    def gliner_labels(self) -> List[str]:
        return [s.strip() for s in self.gliner_labels_csv.split(",") if s.strip()]

    # Phase 2 relation extraction
    relation_min_confidence: float = Field(
        alias="RELATION_MIN_CONFIDENCE", default=0.7
    )
    relation_extraction_token_budget: int = Field(
        alias="RELATION_TOKEN_BUDGET", default=50_000
    )
    relation_queue_backpressure_depth: int = Field(
        alias="RELATION_QUEUE_BACKPRESSURE_DEPTH", default=100
    )

    # Phase 2 document intelligence
    intelligence_map_reduce_token_threshold: int = Field(
        alias="INTELLIGENCE_MAP_REDUCE_TOKEN_THRESHOLD", default=8000
    )

    # Credibility scoring (claim-extraction / contradiction-detection /
    # cross-source-agreement signals were removed alongside Conflicts).
    credibility_weight_recency: float = Field(
        alias="CREDIBILITY_WEIGHT_RECENCY", default=0.30
    )
    credibility_weight_source_type: float = Field(
        alias="CREDIBILITY_WEIGHT_SOURCE_TYPE", default=0.40
    )
    credibility_weight_citation_density: float = Field(
        alias="CREDIBILITY_WEIGHT_CITATION_DENSITY", default=0.30
    )
    credibility_cohort_redis_lock_ttl_s: int = Field(
        alias="CREDIBILITY_COHORT_REDIS_LOCK_TTL_S", default=60
    )
    credibility_cohort_max_neighbors: int = Field(
        alias="CREDIBILITY_COHORT_MAX_NEIGHBORS", default=50
    )

    # Phase 3.1 – Hybrid retrieval
    reranker_enabled: bool = Field(alias="RERANKER_ENABLED", default=True)
    reranker_model: str = Field(
        alias="RERANKER_MODEL", default="BAAI/bge-reranker-base"
    )
    bm25_top_k: int = Field(alias="BM25_TOP_K", default=50)
    vector_top_k: int = Field(alias="VECTOR_TOP_K", default=50)
    rrf_k: int = Field(alias="RRF_K", default=60)
    rerank_top_k: int = Field(alias="RERANK_TOP_K", default=10)

    # Phase 3.3 – Multi-source ingestion
    audio_max_upload_bytes: int = Field(
        alias="AUDIO_MAX_UPLOAD_BYTES", default=524_288_000  # 500 MB
    )
    groq_whisper_model: str = Field(
        alias="GROQ_WHISPER_MODEL", default="whisper-large-v3-turbo"
    )
    notion_access_token: str = Field(alias="NOTION_ACCESS_TOKEN", default="")
    web_scrape_timeout_s: int = Field(alias="WEB_SCRAPE_TIMEOUT_S", default=15)
    zip_max_upload_bytes: int = Field(
        alias="ZIP_MAX_UPLOAD_BYTES", default=524_288_000  # 500 MB
    )
    zip_max_files: int = Field(alias="ZIP_MAX_FILES", default=50)

    # Observability
    sentry_dsn_backend: str = Field(alias="SENTRY_DSN_BACKEND", default="")
    metrics_token: str = Field(alias="METRICS_TOKEN", default="")
    log_level: str = Field(alias="LOG_LEVEL", default="INFO")
    environment: str = Field(alias="ENVIRONMENT", default="development")

    # ─── Phase 5: Media production engine ───────────────────────────────────
    ffmpeg_path: str = Field(alias="FFMPEG_PATH", default="")
    media_data_dir: str = Field(alias="MEDIA_DATA_DIR", default="")
    media_user_quota_bytes: int = Field(
        alias="MEDIA_USER_QUOTA_BYTES", default=2_147_483_648
    )
    reel_worker_concurrency: int = Field(alias="REEL_WORKER_CONCURRENCY", default=2)

    # Daily generation caps (Track H quota service enforces these)
    reel_daily_cap: int = Field(alias="REEL_DAILY_CAP", default=10)
    narration_daily_cap: int = Field(alias="NARRATION_DAILY_CAP", default=50)
    storyboard_daily_cap: int = Field(alias="STORYBOARD_DAILY_CAP", default=20)
    meme_daily_cap: int = Field(alias="MEME_DAILY_CAP", default=100)

    # Render limits (Track A enforces — used by quota check)
    reel_max_duration_seconds: int = Field(
        alias="REEL_MAX_DURATION_SECONDS", default=90
    )
    reel_long_max_duration_seconds: int = Field(
        alias="REEL_LONG_MAX_DURATION_SECONDS", default=900
    )
    narration_max_duration_seconds: int = Field(
        alias="NARRATION_MAX_DURATION_SECONDS", default=180
    )
    storyboard_max_frames: int = Field(alias="STORYBOARD_MAX_FRAMES", default=12)
    meme_max_variants: int = Field(alias="MEME_MAX_VARIANTS", default=8)

    # Optional paid upgrade API keys — features fall back to free providers
    elevenlabs_api_key: str = Field(alias="ELEVENLABS_API_KEY", default="")
    openai_api_key: str = Field(alias="OPENAI_API_KEY", default="")
    stability_api_key: str = Field(alias="STABILITY_API_KEY", default="")
    mubert_api_key: str = Field(alias="MUBERT_API_KEY", default="")
    huggingface_api_key: str = Field(alias="HUGGINGFACE_API_KEY", default="")
    pexels_api_key: str = Field(alias="PEXELS_API_KEY", default="")

    @property
    def resolved_media_data_dir(self) -> str:
        """Compute media_data_dir, falling back to {storage_dir}/../generated."""
        from pathlib import Path

        if self.media_data_dir:
            return self.media_data_dir
        sd = Path(self.storage_dir).resolve()
        # storage_dir is typically ./data/files — put generated alongside as ./data/generated
        return str(sd.parent / "generated")

@lru_cache
def get_settings() -> Settings:
    return Settings()
