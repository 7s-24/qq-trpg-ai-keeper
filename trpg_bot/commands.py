from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ParsedCommand:
    command: str
    args: str


def parse_command(text: str) -> ParsedCommand | None:
    stripped = text.strip()
    if not stripped.startswith("."):
        return None
    if not stripped:
        return None
    parts = stripped.split(maxsplit=1)
    return ParsedCommand(command=parts[0], args=parts[1] if len(parts) > 1 else "")
