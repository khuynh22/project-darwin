from __future__ import annotations

from functools import lru_cache
from pathlib import Path

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

    error_threshold: int = 3

    # All models go through OpenRouter (OpenAI-compatible). Per-session BYOK key;
    # the setting below is only an operator/CLI fallback.
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "anthropic/claude-opus-4.7"

    encryption_key: str = ""
    min_agents: int = 3
    max_agents: int = 10


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


# Default roster — empty. Users must configure agents via the UI (POST /configure).
# The simulation will not start until at least min_agents are configured.
AGENT_ROSTER: list[dict] = []

# Fixed session id used by the CLI runner (scripts/run_simulation.py) and the
# default for non-web code paths. Web sessions use random slugs.
CLI_SESSION_ID = "cli"
