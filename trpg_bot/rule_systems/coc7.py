from __future__ import annotations

from typing import Any

from trpg_bot import simple_yaml as yaml

from trpg_bot.dice import roll_dice
from trpg_bot.models import CheckResult, DiceRoll
from trpg_bot.rule_systems.base import BaseRuleSystem

COC7_TEMPLATE: dict[str, Any] = {
    "system": "COC7",
    "player": "",
    "character_name": "",
    "occupation": "",
    "attributes": {"STR": 0, "CON": 0, "SIZ": 0, "DEX": 0, "APP": 0, "INT": 0, "POW": 0, "EDU": 0},
    "derived": {"HP": 0, "MP": 0, "SAN": 0, "LUCK": 0, "MOV": 0},
    "skills": {"侦查": 0, "聆听": 0, "图书馆使用": 0, "心理学": 0, "话术": 0, "说服": 0, "潜行": 0, "开锁": 0, "医学": 0, "神秘学": 0, "克苏鲁神话": 0},
    "inventory": [],
    "backstory": "",
    "notes": "",
}


class COC7RuleSystem(BaseRuleSystem):
    name = "COC7"

    def parse_roll_command(self, command: str, args: str) -> str | None:
        if command == ".r":
            return args.strip() or "1d100"
        if command == ".ra":
            return "1d100"
        return None

    def roll(self, expression: str) -> DiceRoll:
        return roll_dice(expression)

    def check(self, name: str, character_card: dict[str, Any] | None = None, args: str = "") -> CheckResult:
        card = character_card or {}
        skills = card.get("skills") or {}
        target = _extract_target(name, skills)
        character_name = str(card.get("character_name") or card.get("player") or "未命名角色")
        roll = roll_dice("1d100")
        level, success = coc7_success_level(roll.total, target)
        return CheckResult(system=self.name, name=name, character_name=character_name, roll=roll, target=target, dc=None, success_level=level, success=success)

    def render_check_result(self, result: CheckResult) -> str:
        target_text = "未找到技能值" if result.target is None else str(result.target)
        return "\n".join([
            f"{result.name}检定",
            f"角色：{result.character_name}",
            f"技能值：{target_text}",
            f"骰点：{result.roll.total}",
            f"原始点数：{result.roll.dice}",
            f"修正值：{result.roll.modifier:+d}",
            f"结果：{result.success_level}",
        ])

    def get_character_template(self) -> str:
        return yaml.safe_dump(COC7_TEMPLATE, allow_unicode=True, sort_keys=False)

    def validate_character_card(self, card: dict[str, Any]) -> tuple[bool, list[str]]:
        errors: list[str] = []
        if str(card.get("system", "")).upper() not in {"COC", "COC7"}:
            errors.append("system 必须是 COC7")
        if not isinstance(card.get("skills"), dict):
            errors.append("skills 必须是映射")
        for field in ("player", "character_name"):
            if field not in card:
                errors.append(f"缺少字段：{field}")
        return not errors, errors


def _extract_target(name: str, skills: dict[str, Any]) -> int | None:
    value = skills.get(name)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def coc7_success_level(roll: int, target: int | None) -> tuple[str, bool]:
    if target is None:
        return "无法判定（未找到技能值）", False
    # 常见 COC7 大失败：技能值 < 50 时 96-100，大于等于 50 时 100。后续可做成团配置。
    if (target < 50 and roll >= 96) or (target >= 50 and roll == 100):
        return "大失败", False
    if roll == 1:
        return "大成功", True
    if roll <= max(1, target // 5):
        return "极难成功", True
    if roll <= max(1, target // 2):
        return "困难成功", True
    if roll <= target:
        return "普通成功", True
    return "失败", False
