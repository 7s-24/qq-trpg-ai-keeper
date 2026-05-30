from __future__ import annotations

import re
from typing import Any

from trpg_bot import simple_yaml as yaml

from trpg_bot.dice import roll_dice
from trpg_bot.models import CheckResult, DiceRoll
from trpg_bot.rule_systems.base import BaseRuleSystem

DND5E_TEMPLATE: dict[str, Any] = {
    "system": "DND5E", "player": "", "character_name": "", "race": "", "class": "", "level": 1,
    "attributes": {"STR": 10, "DEX": 10, "CON": 10, "INT": 10, "WIS": 10, "CHA": 10},
    "combat": {"HP": 0, "AC": 0, "initiative": 0, "speed": 0},
    "saving_throws": {}, "skills": {}, "spells": [], "inventory": [], "backstory": "", "notes": "",
}
ATTRIBUTE_ALIASES = {"力量": "STR", "敏捷": "DEX", "体质": "CON", "智力": "INT", "感知": "WIS", "魅力": "CHA"}


class DND5ERuleSystem(BaseRuleSystem):
    name = "DND5E"

    def parse_roll_command(self, command: str, args: str) -> str | None:
        if command in {".rd", ".r"}:
            return args.strip() or "1d20"
        return None

    def roll(self, expression: str) -> DiceRoll:
        return roll_dice(expression)

    def check(self, name: str, character_card: dict[str, Any] | None = None, args: str = "") -> CheckResult:
        dc_match = re.search(r"DC\s*(\d+)", args, re.IGNORECASE)
        dc = int(dc_match.group(1)) if dc_match else None
        card = character_card or {}
        modifier = _modifier_for(name, card)
        expr = f"1d20{modifier:+d}" if modifier else "1d20"
        roll = roll_dice(expr)
        success = dc is not None and roll.total >= dc
        level = "成功" if success else ("失败" if dc is not None else "无法判定（缺少 DC）")
        return CheckResult(self.name, name, str(card.get("character_name") or "未命名角色"), roll, None, dc, level, success, {"modifier": modifier})

    def render_check_result(self, result: CheckResult) -> str:
        return "\n".join([
            f"{result.name}检定",
            f"角色：{result.character_name}",
            f"DC：{result.dc if result.dc is not None else '未指定'}",
            f"骰点：{result.roll.dice}",
            f"修正值：{result.roll.modifier:+d}",
            f"最终结果：{result.roll.total}",
            f"结果：{result.success_level}",
        ])

    def get_character_template(self) -> str:
        return yaml.safe_dump(DND5E_TEMPLATE, allow_unicode=True, sort_keys=False)

    def validate_character_card(self, card: dict[str, Any]) -> tuple[bool, list[str]]:
        errors = []
        if str(card.get("system", "")).upper() not in {"DND", "DND5E"}:
            errors.append("system 必须是 DND5E")
        if not isinstance(card.get("attributes"), dict):
            errors.append("attributes 必须是映射")
        return not errors, errors


def _modifier_for(name: str, card: dict[str, Any]) -> int:
    attrs = card.get("attributes") or {}
    skills = card.get("skills") or {}
    if name in skills:
        return int(skills[name])
    attr = ATTRIBUTE_ALIASES.get(name, name.upper())
    if attr in attrs:
        return (int(attrs[attr]) - 10) // 2
    return 0
