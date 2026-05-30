from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from trpg_bot.models import ReplyMode, RuleSystemName


@dataclass(slots=True)
class Settings:
    data_dir: Path = Path("data")
    database_path: Path = Path("data/trpg.sqlite3")
    superusers: set[str] = field(default_factory=set)
    default_kps: set[str] = field(default_factory=set)
    default_reply_mode: ReplyMode = ReplyMode.MANUAL
    default_rule_system: RuleSystemName = RuleSystemName.COC7
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4o-mini"
    ai_timeout_seconds: int = 60

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        for child in ("campaigns", "logs", "characters"):
            (self.data_dir / child).mkdir(parents=True, exist_ok=True)


def _env(name: str, default: str = "") -> str:
    return os.getenv(f"TRPG_{name}", default)


def _parse_set(value: str) -> set[str]:
    return {part.strip() for part in value.split(",") if part.strip()}


@lru_cache
def get_settings() -> Settings:
    settings = Settings(
        data_dir=Path(_env("DATA_DIR", "data")),
        database_path=Path(_env("DATABASE_PATH", "data/trpg.sqlite3")),
        superusers=_parse_set(_env("SUPERUSERS", "")),
        default_kps=_parse_set(_env("DEFAULT_KPS", "")),
        default_reply_mode=ReplyMode(_env("DEFAULT_REPLY_MODE", "manual")),
        default_rule_system=RuleSystemName.from_command(_env("DEFAULT_RULE_SYSTEM", "COC7")),
        ai_base_url=_env("AI_BASE_URL", "https://api.openai.com/v1"),
        ai_api_key=_env("AI_API_KEY", ""),
        ai_model=_env("AI_MODEL", "gpt-4o-mini"),
        ai_timeout_seconds=int(_env("AI_TIMEOUT_SECONDS", "60")),
    )
    settings.ensure_dirs()
    return settings
