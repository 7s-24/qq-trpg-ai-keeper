from __future__ import annotations

import random
import re
from dataclasses import replace

from trpg_bot.models import DiceRoll

DICE_RE = re.compile(r"^\s*(?:(?P<count>\d{1,3})d(?P<sides>\d{1,5})|d(?P<sides_only>\d{1,5}))\s*(?P<mod>[+-]\s*\d+)?\s*$", re.IGNORECASE)


class DiceExpressionError(ValueError):
    pass


def parse_dice_expression(expression: str) -> tuple[int, int, int]:
    match = DICE_RE.match(expression)
    if not match:
        raise DiceExpressionError("骰点格式错误，请使用如 1d100、d20、1d20+3、2d6-1 的格式。")
    count = int(match.group("count") or 1)
    sides = int(match.group("sides") or match.group("sides_only"))
    modifier = int((match.group("mod") or "0").replace(" ", ""))
    if count <= 0 or count > 100:
        raise DiceExpressionError("骰子数量必须在 1 到 100 之间。")
    if sides <= 1 or sides > 100000:
        raise DiceExpressionError("骰子面数必须在 2 到 100000 之间。")
    return count, sides, modifier


def roll_dice(expression: str, rng: random.Random | None = None) -> DiceRoll:
    count, sides, modifier = parse_dice_expression(expression)
    random_source = rng or random.SystemRandom()
    dice = [random_source.randint(1, sides) for _ in range(count)]
    normalized = f"{count}d{sides}{modifier:+d}" if modifier else f"{count}d{sides}"
    return DiceRoll(expression=normalized, dice=dice, modifier=modifier, total=sum(dice) + modifier, sides=sides, count=count)


def with_forced_roll(base: DiceRoll, dice: list[int], modifier: int | None = None) -> DiceRoll:
    mod = base.modifier if modifier is None else modifier
    return replace(base, dice=dice, modifier=mod, total=sum(dice) + mod)


def render_roll(roll: DiceRoll) -> str:
    return "\n".join([
        f"骰子表达式：{roll.expression}",
        f"原始点数：{roll.dice}",
        f"修正值：{roll.modifier:+d}",
        f"最终结果：{roll.total}",
    ])
