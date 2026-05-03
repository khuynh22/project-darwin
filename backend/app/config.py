from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://darwin:darwin@localhost:5432/darwin"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "info"

    starting_capital: float = 10.00
    survival_tax: float = 0.50
    tax_interval_turns: int = 10
    max_turns: int = 500
    apex_wealth_fraction: float = 0.90

    stub_mode: bool = True

    error_threshold: int = 3

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    grok_api_key: str = ""

    anthropic_model: str = "claude-opus-4-7"
    openai_model: str = "gpt-5"
    google_model: str = "gemini-2.5-pro"
    grok_model: str = "grok-3"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma4"

    chroma_path: str = "./chroma"

    encryption_key: str = ""
    min_agents: int = 3
    max_agents: int = 10


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Default roster — empty. Users must configure agents via the UI (POST /configure).
# The simulation will not start until at least min_agents are configured.
AGENT_ROSTER: list[dict] = []
