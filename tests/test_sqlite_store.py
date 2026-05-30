from pathlib import Path

from trpg_bot.memory.sqlite_store import SQLiteStore


def test_memory_upsert_updates_existing_title(tmp_path: Path):
    store = SQLiteStore(tmp_path / "test.sqlite3")
    store.add_memory("c1", "npc", "老王", "第一次记录", ["a"], 1)
    store.upsert_memory("c1", "npc", "老王", "更新后的记录", ["b"], 2)
    rows = store.search_memories("c1", ["老王", "更新"], limit=10)
    assert len(rows) == 1
    assert rows[0]["content"] == "更新后的记录"
    assert rows[0]["source_turn_id"] == 2
