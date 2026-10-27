from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or a .env file)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/docuquery"

    # Auth
    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    jwt_expire_minutes: int = 60 * 8

    # LLM provider: "openai" = any OpenAI-compatible API (Ollama, OpenAI, vLLM, ...)
    #               "fake"   = deterministic offline provider for tests and demos
    llm_provider: str = "openai"
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    chat_model: str = "llama3.2"
    embedding_model: str = "nomic-embed-text"
    embedding_dim: int = 768

    # Retrieval
    chunk_size: int = 900          # characters per chunk
    chunk_overlap: int = 150       # characters shared between neighbouring chunks
    top_k: int = 5
    min_similarity: float = 0.25   # below this, the assistant says it doesn't know

    max_upload_mb: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
