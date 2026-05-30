import random

import pytest

from trpg_bot.dice import DiceExpressionError, parse_dice_expression, roll_dice


def test_parse_dice_expression_with_modifier():
    assert parse_dice_expression("1d100+10") == (1, 100, 10)
    assert parse_dice_expression("d20 - 1") == (1, 20, -1)


def test_roll_dice_is_deterministic_with_rng():
    roll = roll_dice("1d6+2", rng=random.Random(1))
    assert roll.dice == [2]
    assert roll.total == 4
    assert roll.expression == "1d6+2"


def test_bad_expression_has_clear_error():
    with pytest.raises(DiceExpressionError):
        parse_dice_expression("hello")
