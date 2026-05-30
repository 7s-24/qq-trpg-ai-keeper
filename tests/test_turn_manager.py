from pathlib import Path

from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.models import ReplyMode
from trpg_bot.turn_manager import TurnManager


def test_buffer_and_required_players(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TRPG_DATABASE_PATH", str(tmp_path / "test.sqlite3"))
    store = SQLiteStore(tmp_path / "test.sqlite3")
    manager = TurnManager(store)
    settings = manager.add_player("100", "u1")
    settings.reply_mode = ReplyMode.AUTO
    store.save_settings(settings)
    manager.set_required("100", {"u1"})
    manager.buffer_message("100", "u1", "玩家1", "我调查房间")
    assert manager.has_all_required_spoken(manager.get_settings("100"))
    assert "我调查房间" in manager.render_buffer("100")


def test_clear_buffer(tmp_path: Path):
    store = SQLiteStore(tmp_path / "test.sqlite3")
    manager = TurnManager(store)
    manager.buffer_message("100", "u1", "玩家1", "行动")
    manager.clear_buffer("100")
    assert manager.list_buffer("100") == []
