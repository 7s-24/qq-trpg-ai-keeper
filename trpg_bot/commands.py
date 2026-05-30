from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class ParsedCommand:
    command: str
    args: str


@dataclass(slots=True)
class ParsedCheckCommand:
    name: str
    rest: str
    dc: int | None = None


def parse_command(text: str) -> ParsedCommand | None:
    stripped = text.strip()
    if not stripped.startswith("."):
        return None
    if not stripped:
        return None
    parts = stripped.split(maxsplit=1)
    return ParsedCommand(command=parts[0], args=parts[1] if len(parts) > 1 else "")


def parse_check_command_args(command: str, args: str) -> ParsedCheckCommand:
    """Parse .ra/.检定 arguments without depending on NoneBot event code."""
    stripped = args.strip()
    if not stripped:
        example = ".ra 侦查" if command == ".ra" else ".检定 侦查 或 .检定 力量 DC15"
        raise ValueError(f"请指定检定名称，例如：{example}。")
    parts = stripped.split(maxsplit=1)
    name = parts[0]
    rest = parts[1] if len(parts) > 1 else stripped
    dc = None
    dc_match = re.search(r"\bDC\s*(\d+)\b", stripped, re.IGNORECASE)
    if dc_match:
        dc = int(dc_match.group(1))
    return ParsedCheckCommand(name=name, rest=rest, dc=dc)
