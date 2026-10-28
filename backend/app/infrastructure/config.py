from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ARENA_", env_file=".env", extra="ignore")
    mode: Literal["mock"] = "mock"
    database_url: str = "postgresql+psycopg://arena:arena_local@127.0.0.1:55433/arena"
    redis_url: str = "redis://127.0.0.1:56379/0"
    model_timeout_seconds: float = Field(default=1.0, ge=0.05, le=30)
    lease_seconds: int = Field(default=15, ge=3, le=300)
    poll_seconds: float = Field(default=1, ge=0.05, le=10)
    max_attempts: int = Field(default=3, ge=1, le=5)
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
