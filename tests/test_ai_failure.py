import asyncio
from pathlib import Path

from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.turn_manager import TurnManager


class FailingAI:
    async def generate_reply(self, *args, **kwargs):
        raise RuntimeError("boom")


def test_ai_failure_keeps_current_turn_and_buffer(tmp_path: Path):
    store = SQLiteStore(tmp_path / "test.sqlite3")
    manager = TurnManager(store)
    manager.ai = FailingAI()
    manager.buffer_message("100", "u1", "玩家1", "我开门")
    before = manager.get_settings("100").current_turn_id
    reply = asyncio.run(manager.finalize_turn("100", force=True))
    after = manager.get_settings("100").current_turn_id
    assert "AI 结算失败" in reply.reply
    assert before == after
    assert "我开门" in manager.render_buffer("100")
