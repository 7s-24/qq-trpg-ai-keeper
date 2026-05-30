from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class MemoryItem:
    type: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
