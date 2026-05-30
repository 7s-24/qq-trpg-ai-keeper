from __future__ import annotations

import json
import logging
import re
from typing import Any

from trpg_bot.models import AIReply

logger = logging.getLogger(__name__)

DEFAULT_MEMORY = {"session_log": [], "characters": [], "npcs": [], "locations": [], "clues": [], "world_state": [], "unresolved_threads": []}


def parse_ai_output(text: str) -> AIReply:
    raw = text.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                logger.exception("AI JSON fallback parse failed")
                return AIReply(reply=raw, memory_update=DEFAULT_MEMORY.copy(), next_turn_required_players=[], raw_text=raw, parse_error=str(exc))
        else:
            return AIReply(reply=raw, memory_update=DEFAULT_MEMORY.copy(), next_turn_required_players=[], raw_text=raw, parse_error="未找到 JSON 对象")
    if not isinstance(data, dict):
        return AIReply(reply=raw, memory_update=DEFAULT_MEMORY.copy(), next_turn_required_players=[], raw_text=raw, parse_error="JSON 顶层不是对象")
    reply = str(data.get("reply") or raw)
    memory_update = _normalize_memory(data.get("memory_update"))
    next_turn = data.get("next_turn") if isinstance(data.get("next_turn"), dict) else {}
    required = [str(x) for x in next_turn.get("required_players", [])] if isinstance(next_turn.get("required_players", []), list) else []
    dice_requests = data.get("dice_requests") if isinstance(data.get("dice_requests"), list) else []
    return AIReply(reply=reply, memory_update=memory_update, next_turn_required_players=required, next_turn_reason=str(next_turn.get("reason") or ""), dice_requests=dice_requests, raw_text=raw)


def _normalize_memory(value: Any) -> dict[str, list[Any]]:
    result = DEFAULT_MEMORY.copy()
    if isinstance(value, dict):
        for key in result:
            if isinstance(value.get(key), list):
                result[key] = value[key]
    return result
