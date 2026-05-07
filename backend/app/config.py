from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LLM_PROVIDER: str = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4.1-mini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/story_insights"
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080
    AUTH_COOKIE_ENABLED: bool = True
    AUTH_COOKIE_NAME: str = "access_token"
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "lax"
    AUTH_COOKIE_MAX_AGE_MINUTES: int = 10080
    AUTH_RETURN_TOKEN_IN_BODY: bool = False
    AUTH_ALLOW_TOKEN_RESPONSE_OVERRIDE: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    REPORT_LLM_SUMMARY_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_SALT: str = "change-me-for-user-hashing"
    METRICS_ENABLED: bool = True
    PROVIDER_HEALTH_WINDOW: int = 50
    SLOW_SCENE_GENERATION_MS: int = 3000
    FEEDBACK_ENABLED: bool = True
    FEEDBACK_COMMENT_MAX_CHARS: int = 300
    ANALYSIS_NLP_ENABLED: bool = True
    ANALYSIS_SENTIMENT_ENABLED: bool = True
    ANALYSIS_TOPIC_TAGS_ENABLED: bool = True
    ANALYSIS_PII_REDACTION_ENABLED: bool = True
    ANALYSIS_COMMENT_MAX_CHARS: int = 300
    FEEDBACK_RAW_RETENTION_DAYS: int = 90
    FEEDBACK_AGGREGATE_RETENTION_DAYS: int = 365
    FEEDBACK_MICRO_PROMPT_ENABLED: bool = True
    FEEDBACK_MICRO_PROMPT_TURN: int = 2
    FEEDBACK_STYLE_HINT_TTL_TURNS: int = 2
    RETRIEVAL_ENABLED: bool = False
    RETRIEVAL_BACKEND: str = "none"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_REVISION: str = ""
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_BATCH_SIZE: int = 64
    EMBEDDING_NORMALIZE: bool = True
    EMBEDDING_CACHE_DIR: str = "./.cache/sentence-transformers"
    FAISS_INDEX_DIR: str = "./data/faiss"
    FAISS_INDEX_NAME: str = "default"
    FAISS_HNSW_M: int = 32
    FAISS_EF_CONSTRUCTION: int = 200
    FAISS_EF_SEARCH: int = 64
    RETRIEVAL_TOP_K: int = 10
    RETRIEVAL_OVERFETCH_K: int = 50
    OBJECT_ARCHIVE_ENABLED: bool = False
    OBJECT_STORAGE_BACKEND: str = "filesystem"
    OBJECT_STORAGE_BUCKET: str = "story-insights"
    OBJECT_STORAGE_PREFIX: str = "story-insights"
    OBJECT_STORAGE_REGION: str = "us-east-1"
    OBJECT_STORAGE_ENDPOINT: str = ""
    OBJECT_STORAGE_ACCESS_KEY: str = ""
    OBJECT_STORAGE_SECRET_KEY: str = ""
    OBJECT_STORAGE_FORCE_PATH_STYLE: bool = True
    OBJECT_STORAGE_SIGNED_URL_TTL_SEC: int = 300
    OBJECT_STORAGE_FILESYSTEM_ROOT: str = "./data/archive"
    ARCHIVE_RAW_TRACES_ENABLED: bool = True
    ARCHIVE_PROMPTS_ENABLED: bool = True
    ARCHIVE_PDFS_ENABLED: bool = False
    ARCHIVE_FAISS_SNAPSHOT_RETENTION_DAYS: int = 14
    ARCHIVE_TRACE_RETENTION_DAYS: int = 30
    ARCHIVE_PROMPT_RETENTION_DAYS: int = 30
    ARCHIVE_PDF_RETENTION_DAYS: int = 7
    BENCHMARK_DEBUG_FIELDS_ENABLED: bool = True
    SECURITY_HEADERS_ENABLED: bool = True
    CSP_CONNECT_SRC: str = "http://localhost:8000 http://localhost:5173"
    PROVIDER_CIRCUIT_BREAKER_ENABLED: bool = True
    PROVIDER_CIRCUIT_FAILURE_THRESHOLD: int = 5
    PROVIDER_CIRCUIT_FAILURE_WINDOW_SEC: int = 30
    PROVIDER_CIRCUIT_OPEN_SEC: int = 60
    PROVIDER_CIRCUIT_HALF_OPEN_MAX_CALLS: int = 1
    BENCHMARK_COMPARISONS_ENABLED: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self):
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
