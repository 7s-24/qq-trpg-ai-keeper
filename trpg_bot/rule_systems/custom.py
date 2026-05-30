from __future__ import annotations

from typing import Any

from trpg_bot import simple_yaml as yaml

from trpg_bot.dice import roll_dice
from trpg_bot.models import CheckResult, DiceRoll
from trpg_bot.rule_systems.base import BaseRuleSystem

CUSTOM_TEMPLATE = {"system": "CUSTOM", "player": "", "character_name": "", "attributes": {}, "skills": {}, "resources": {}, "inventory": [], "backstory": "", "notes": ""}


class CustomRuleSystem(BaseRuleSystem):
    name = "CUSTOM"

    def parse_roll_command(self, command: str, args: str) -> str | None:
        return args.strip() if command == ".r" else None

    def roll(self, expression: str) -> DiceRoll:
        return roll_dice(expression)

    def check(self, name: str, character_card: dict[str, Any] | None = None, args: str = "") -> CheckResult:
        roll = roll_dice("1d100")
        return CheckResult(self.name, name, str((character_card or {}).get("character_name") or "未命名角色"), roll, None, None, "自定义规则：请 KP 判定", False)

    def render_check_result(self, result: CheckResult) -> str:
        return f"{result.name}检定\n角色：{result.character_name}\n骰点：{result.roll.total}\n结果：{result.success_level}"

    def get_character_template(self) -> str:
        return yaml.safe_dump(CUSTOM_TEMPLATE, allow_unicode=True, sort_keys=False)

    def validate_character_card(self, card: dict[str, Any]) -> tuple[bool, list[str]]:
        return isinstance(card, dict), ([] if isinstance(card, dict) else ["角色卡必须是 YAML 映射"])
