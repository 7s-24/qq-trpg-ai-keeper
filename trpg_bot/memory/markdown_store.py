from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trpg_bot.config import get_settings
from trpg_bot.models import TurnMessage

MEMORY_FILE_MAP = {
    "characters": "characters/updates.md",
    "npcs": "npcs.md",
    "locations": "locations.md",
    "clues": "clues.md",
    "world_state": "world_state.md",
    "unresolved_threads": "unresolved_threads.md",
    "session_log": "timeline.md",
}


class MarkdownStore:
    def __init__(self) -> None:
        self.base = get_settings().data_dir / "campaigns"

    def campaign_dir(self, campaign_id: str) -> Path:
        path = self.base / campaign_id
        (path / "session_logs").mkdir(parents=True, exist_ok=True)
        (path / "characters").mkdir(parents=True, exist_ok=True)
        return path

    def append_session_reply(self, campaign_id: str, turn_id: int, messages: list[TurnMessage], reply: str) -> None:
        path = self.campaign_dir(campaign_id) / "session_logs" / f"turn_{turn_id:04d}.md"
        now = datetime.now(timezone.utc).isoformat()
        lines = [f"\n## Turn {turn_id} - {now}\n", "### 玩家发言\n"]
        for msg in messages:
            lines.append(f"- **{msg.nickname}({msg.user_id})**: {msg.content}\n")
        lines.extend(["\n### KP 回复\n", reply.strip() + "\n"])
        with path.open("a", encoding="utf-8") as f:
            f.writelines(lines)

    def append_memory_update(self, campaign_id: str, turn_id: int, memory_update: dict[str, list[Any]]) -> None:
        base = self.campaign_dir(campaign_id)
        now = datetime.now(timezone.utc).isoformat()
        for key, items in memory_update.items():
            if not items:
                continue
            rel = MEMORY_FILE_MAP.get(key, f"{key}.md")
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(f"\n## Turn {turn_id} - {now}\n")
                for item in items:
                    f.write(f"- {item}\n")
