from __future__ import annotations

import re
from difflib import get_close_matches
from typing import Any

from trpg_bot import yaml_compat as yaml

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
SKILL_ALIASES = {
    "观察": "察觉",
    "侦查": "察觉",
    "聆听": "察觉",
    "潜行": "隐匿",
    "隐匿": "隐匿",
    "说服": "游说",
    "话术": "欺瞒",
    "运动": "运动",
    "调查": "调查",
}
STANDARD_SKILLS = [
    "运动", "杂技", "巧手", "隐匿", "奥秘", "历史", "调查", "自然", "宗教", "驯兽", "洞悉", "医药",
    "察觉", "求生", "欺瞒", "威吓", "表演", "游说",
]


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
        resolved_name, suggestions, was_alias = _resolve_name(name, card)
        if resolved_name is None:
            roll = roll_dice("1d20")
            return CheckResult(
                self.name,
                name,
                str(card.get("character_name") or "未命名角色"),
                roll,
                None,
                dc,
                "无法判定（未找到技能）",
                False,
                {"missing_skill": name, "suggestions": suggestions},
            )
        modifier = _modifier_for(resolved_name, card)
        expr = f"1d20{modifier:+d}" if modifier else "1d20"
        roll = roll_dice(expr)
        success = dc is not None and roll.total >= dc
        level = "成功" if success else ("失败" if dc is not None else "无法判定（缺少 DC）")
        return CheckResult(self.name, resolved_name, str(card.get("character_name") or "未命名角色"), roll, None, dc, level, success, {"modifier": modifier, "input_name": name, "was_alias": was_alias})

    def render_check_result(self, result: CheckResult) -> str:
        if result.detail.get("missing_skill"):
            suggestions = " / ".join(result.detail.get("suggestions") or [])
            suffix = f"你是不是想检定：{suggestions}？" if suggestions else "请检查技能名。"
            return f"未找到技能『{result.detail['missing_skill']}』，{suffix}"
        lines = [
            f"{result.name}检定",
            f"角色：{result.character_name}",
            f"DC：{result.dc if result.dc is not None else '未指定'}",
            f"骰点：{result.roll.dice}",
            f"修正值：{result.roll.modifier:+d}",
            f"最终结果：{result.roll.total}",
            f"结果：{result.success_level}",
        ]
        input_name = result.detail.get("input_name")
        if input_name and input_name != result.name:
            lines.insert(1, f"按『{result.name}』判定（输入：{input_name}）")
        if result.dc is None:
            lines.append("提示：DND 检定需要 DC，例如 .检定 察觉 DC15")
        return "\n".join(lines)

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


def _resolve_name(name: str, card: dict[str, Any]) -> tuple[str | None, list[str], bool]:
    stripped = name.strip()
    skills = card.get("skills") or {}
    candidates = list(dict.fromkeys(list(ATTRIBUTE_ALIASES.keys()) + list(ATTRIBUTE_ALIASES.values()) + STANDARD_SKILLS + [str(k) for k in skills.keys()]))
    if stripped in candidates:
        return stripped, [], False
    alias = SKILL_ALIASES.get(stripped)
    if alias and alias in candidates:
        return alias, [], True
    matches = get_close_matches(stripped, candidates, n=3, cutoff=0.55)
    if matches:
        return matches[0], matches, True
    suggestions = get_close_matches(stripped, candidates, n=3, cutoff=0.25) or candidates[:3]
    return None, suggestions, False
