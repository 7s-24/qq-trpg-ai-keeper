from __future__ import annotations

from difflib import get_close_matches
from typing import Any

from trpg_bot import yaml_compat as yaml

from trpg_bot.config import get_settings
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

SKILL_ALIASES = {
    "观察": "侦查",
    "查看": "侦查",
    "寻找": "侦查",
    "听": "聆听",
    "倾听": "聆听",
    "隐匿": "潜行",
    "躲藏": "潜行",
    "潜伏": "潜行",
    "口才": "话术",
    "话术": "话术",
    "交涉": "说服",
    "劝说": "说服",
    "撬锁": "开锁",
    "锁匠": "开锁",
    "图书馆": "图书馆使用",
    "查资料": "图书馆使用",
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
        resolved_name, suggestions, was_alias = _resolve_skill_name(name, skills)
        if resolved_name is None:
            roll = roll_dice("1d100")
            return CheckResult(
                system=self.name,
                name=name,
                character_name=str(card.get("character_name") or card.get("player") or "未命名角色"),
                roll=roll,
                target=None,
                dc=None,
                success_level="无法判定（未找到技能）",
                success=False,
                detail={"missing_skill": name, "suggestions": suggestions},
            )
        target = _extract_target(resolved_name, skills)
        used_default = False
        if target is None:
            target = get_settings().default_skill_value
            used_default = True
        character_name = str(card.get("character_name") or card.get("player") or "未命名角色")
        roll = roll_dice("1d100")
        level, success = coc7_success_level(roll.total, target)
        return CheckResult(
            system=self.name,
            name=resolved_name,
            character_name=character_name,
            roll=roll,
            target=target,
            dc=None,
            success_level=level,
            success=success,
            detail={"input_name": name, "was_alias": was_alias, "used_default": used_default},
        )

    def render_check_result(self, result: CheckResult) -> str:
        if result.detail.get("missing_skill"):
            suggestions = " / ".join(result.detail.get("suggestions") or [])
            suffix = f"你是不是想检定：{suggestions}？" if suggestions else "请检查角色卡技能名或换一个常用技能。"
            return f"未找到技能『{result.detail['missing_skill']}』，{suffix}"
        target_text = "未找到技能值" if result.target is None else str(result.target)
        lines = [
            f"{result.name}检定",
            f"角色：{result.character_name}",
            f"技能值：{target_text}",
            f"骰点：{result.roll.total}",
            f"原始点数：{result.roll.dice}",
            f"修正值：{result.roll.modifier:+d}",
            f"结果：{result.success_level}",
        ]
        input_name = result.detail.get("input_name")
        if input_name and input_name != result.name:
            lines.insert(1, f"按『{result.name}』判定（输入：{input_name}）")
        if result.detail.get("used_default"):
            lines.insert(3, f"说明：未找到角色卡技能值，使用默认值 {result.target}")
        return "\n".join(lines)

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


def _resolve_skill_name(name: str, skills: dict[str, Any]) -> tuple[str | None, list[str], bool]:
    stripped = name.strip()
    standard = list(COC7_TEMPLATE["skills"].keys())
    candidates = list(dict.fromkeys(standard + [str(k) for k in skills.keys()]))
    if stripped in candidates:
        return stripped, [], False
    alias = SKILL_ALIASES.get(stripped)
    if alias and alias in candidates:
        return alias, [], True
    matches = get_close_matches(stripped, candidates, n=3, cutoff=0.55)
    if matches:
        return matches[0], matches, True
    suggestions = get_close_matches(stripped, candidates, n=3, cutoff=0.25)
    if not suggestions:
        suggestions = candidates[:3]
    return None, suggestions, False


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
