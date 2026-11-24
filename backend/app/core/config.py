from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AurenOps"
    env: str = "dev"
    database_url: str = "postgresql+psycopg://auren:auren@localhost:5432/aurenops"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me"
    jwt_alg: str = "HS256"
    access_token_minutes: int = 60
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    embedding_backend: str = "hash"  # hash | st
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    approval_ttl_hours: int = 24
    tool_timeout_seconds: int = 20
    rate_limit_per_minute: int = 240
    minutes_saved_per_email: int = 6  # ESTIMATE used only for the "time saved" metric
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def pg_conninfo(self) -> str:
        return self.database_url.replace("+psycopg", "")


settings = Settings()
