from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://ocr4all:ocr4all@localhost:5432/ocr4all"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    storage_path: str = "./storage"
    storage_type: str = "local"  # "local" or "s3"

    # S3/MinIO
    s3_endpoint: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "ocr4all"

    # Tesseract
    tesseract_cmd: str | None = None
    tesseract_lang: str = "spa+eng"

    # LLM
    llm_provider: str = "ollama"  # "ollama" or "openai"
    llm_model: str = "llama3.2"
    llm_base_url: str = "http://localhost:11434"
    llm_api_key: str | None = None
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1000
    llm_timeout: int = 60

    # API
    api_prefix: str = "/api/v1"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
