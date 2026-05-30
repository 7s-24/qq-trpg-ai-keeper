from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from trpg_bot.models import CheckResult, DiceRoll


class BaseRuleSystem(ABC):
    name: str

    @abstractmethod
    def parse_roll_command(self, command: str, args: str) -> str | None:
        """Return a dice expression if this command maps to a roll."""

    @abstractmethod
    def roll(self, expression: str) -> DiceRoll:
        pass

    @abstractmethod
    def check(self, name: str, character_card: dict[str, Any] | None = None, args: str = "") -> CheckResult:
        pass

    @abstractmethod
    def render_check_result(self, result: CheckResult) -> str:
        pass

    @abstractmethod
    def get_character_template(self) -> str:
        pass

    @abstractmethod
    def validate_character_card(self, card: dict[str, Any]) -> tuple[bool, list[str]]:
        pass
