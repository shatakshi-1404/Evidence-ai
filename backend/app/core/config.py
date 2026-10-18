from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-only-change-me-use-a-long-random-value"


class Settings(BaseSettings):
    app_name: str = "EvidenceAI"
    app_version: str = "1.0.0"
    environment: str = "development"

    cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str = "postgresql://evidenceai:evidenceai@localhost:5432/evidenceai"
    redis_url: str = "redis://localhost:6379/0"

    # Authentication
    secret_key: str = DEV_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    cookie_name: str = "evidenceai_session"
    cookie_secure: bool | None = None  # None = Secure only in production (needs HTTPS)

    # Rate limits, in requests per minute (0 disables a limit)
    rate_limit_ask_per_minute: int = 20
    rate_limit_search_per_minute: int = 60
    rate_limit_auth_per_minute: int = 10

    # Uploads and ingestion
    upload_dir: str = "./data/uploads"
    max_upload_mb: int = 10
    chunk_size: int = 1000
    chunk_overlap: int = 200
    max_ingest_attempts: int = 3
    retry_base_seconds: int = 5
    stale_processing_minutes: int = 10
    queued_sweep_minutes: int = 5

    # Embeddings. Vectors must be 384-dimensional (see models/chunk.py).
    embedding_provider: str = "sentence_transformers"  # or "hash" (offline, used in tests)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_query_prefix: str = "Represent this sentence for searching relevant passages: "
    embedding_batch_size: int = 32

    # Retrieval
    retrieval_candidates: int = 30
    retrieval_top_k: int = 6
    rrf_k: int = 60
    min_similarity: float = 0.50

    # Answer generation: "extractive" (no model) or "openai_compatible"
    llm_provider: str = "extractive"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = "gpt-4o-mini"
    llm_timeout_seconds: int = 60
    llm_max_retries: int = 2  # extra attempts when the provider says "rate limited" (429)

    # Evaluation
    eval_report_path: str = "./data/eval/latest.json"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def sqlalchemy_database_url(self) -> str:
        """SQLAlchemy needs to be told which Postgres driver to use (psycopg 3)."""
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def use_secure_cookie(self) -> bool:
        if self.cookie_secure is not None:
            return self.cookie_secure
        return self.environment == "production"

    @model_validator(mode="after")
    def _no_default_secret_in_production(self) -> "Settings":
        if self.environment == "production" and self.secret_key == DEV_SECRET:
            raise ValueError("Set a strong SECRET_KEY before running in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
