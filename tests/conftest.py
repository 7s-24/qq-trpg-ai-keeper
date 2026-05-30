from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from trpg_bot.ai.client import AIClient
from trpg_bot.character_cards import CharacterCardStore
from trpg_bot.config import get_settings
from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.turn_manager import TurnManager


@pytest.fixture
def temp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "database_path", tmp_path / "test.sqlite3")
    monkeypatch.setattr(settings, "superusers", set())
    monkeypatch.setattr(settings, "ai_api_key", "")
    monkeypatch.setattr(settings, "default_skill_value", 50)
    settings.ensure_dirs()
    return settings


@pytest.fixture
def temp_store(temp_settings) -> SQLiteStore:
    return SQLiteStore(temp_settings.database_path)


@pytest.fixture
def turn_manager(temp_store: SQLiteStore) -> TurnManager:
    return TurnManager(temp_store)


@pytest.fixture
def isolated_core(temp_settings, temp_store: SQLiteStore, monkeypatch: pytest.MonkeyPatch) -> TurnManager:
    import trpg_bot.core_handler as core

    manager = TurnManager(temp_store)
    cards = CharacterCardStore(temp_store)
    monkeypatch.setattr(core, "store", temp_store)
    monkeypatch.setattr(core, "turn_manager", manager)
    monkeypatch.setattr(core, "card_store", cards)
    return manager


@pytest.fixture
def mock_ai_client(temp_settings):
    captured: dict[str, Any] = {}

    def factory(content: str | dict[str, Any], status: int = 200, exc: Exception | None = None) -> tuple[AIClient, dict[str, Any]]:
        text = json.dumps(content, ensure_ascii=False) if isinstance(content, dict) else content

        def handler(request: httpx.Request) -> httpx.Response:
            captured["payload"] = json.loads(request.content.decode())
            if exc:
                raise exc
            return httpx.Response(status, json={"choices": [{"message": {"content": text}}]}, request=request)

        temp_settings.ai_api_key = "test-key"
        return AIClient(transport=httpx.MockTransport(handler)), captured

    return factory

