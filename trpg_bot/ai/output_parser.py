from __future__ import annotations

import json
import logging
import re
from typing import Any

from trpg_bot.models import AIReply, DiceRequest, RuleSystemName

logger = logging.getLogger(__name__)

DEFAULT_MEMORY = {"session_log": [], "characters": [], "npcs": [], "locations": [], "clues": [], "world_state": [], "unresolved_threads": []}


def parse_ai_output(text: str, rule_system: RuleSystemName | str = RuleSystemName.COC7) -> AIReply:
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
    dice_requests = _normalize_dice_requests(data.get("dice_requests"), rule_system)
    return AIReply(reply=reply, memory_update=memory_update, next_turn_required_players=required, next_turn_reason=str(next_turn.get("reason") or ""), dice_requests=dice_requests, raw_text=raw)


def _normalize_memory(value: Any) -> dict[str, list[Any]]:
    result = DEFAULT_MEMORY.copy()
    if isinstance(value, dict):
        for key in result:
            if isinstance(value.get(key), list):
                result[key] = value[key]
    return result


def _normalize_dice_requests(value: Any, rule_system: RuleSystemName | str) -> list[DiceRequest]:
    if not isinstance(value, list):
        return []
    try:
        system = RuleSystemName.from_command(str(rule_system))
    except ValueError:
        system = RuleSystemName.COC7
    requests: list[DiceRequest] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        user_id = str(item.get("user_id") or "").strip()
        if not user_id:
            continue
        reason = str(item.get("reason") or "").strip()
        skill = str(item.get("skill") or reason or "检定").strip()
        suggested_command = str(item.get("suggested_command") or "").strip()
        if not suggested_command:
            suggested_command = _default_suggested_command(system, skill)
        requests.append(DiceRequest(user_id=user_id, skill=skill, reason=reason, suggested_command=suggested_command))
    return requests


def _default_suggested_command(system: RuleSystemName, skill: str) -> str:
    if system == RuleSystemName.DND5E:
        return f".检定 {skill} DC?"
    if system == RuleSystemName.CUSTOM:
        return f".检定 {skill}"
    return f".ra {skill}"
