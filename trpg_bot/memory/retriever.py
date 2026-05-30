from __future__ import annotations

from typing import Any

from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.utils import keywords_from_text


class MemoryRetriever:
    """Keyword retriever now; interface kept small for future vector retrieval."""

    def __init__(self, sqlite: SQLiteStore | None = None) -> None:
        self.sqlite = sqlite or SQLiteStore()

    def retrieve(self, campaign_id: str, texts: list[str], limit: int = 8) -> list[dict[str, Any]]:
        keywords: list[str] = []
        for text in texts:
            for kw in keywords_from_text(text):
                if kw not in keywords:
                    keywords.append(kw)
        return self.sqlite.search_memories(campaign_id, keywords, limit=limit)
