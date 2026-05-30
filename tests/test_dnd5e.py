from trpg_bot.dice import parse_dice_expression
from trpg_bot.models import DiceRoll
from trpg_bot.rule_systems.dnd5e import DND5ERuleSystem


def test_dnd_strength_check_dc15(monkeypatch):
    def fixed_roll(expression: str) -> DiceRoll:
        assert expression == "1d20+3"
        return DiceRoll(expression, [12], 3, 15, 20, 1)

    monkeypatch.setattr("trpg_bot.rule_systems.dnd5e.roll_dice", fixed_roll)
    result = DND5ERuleSystem().check("力量", {"character_name": "战士", "attributes": {"STR": 16}}, args="DC15")
    assert result.dc == 15
    assert result.roll.modifier == 3
    assert result.success_level == "成功"


def test_dnd_perception_check_dc12(monkeypatch):
    def fixed_roll(expression: str) -> DiceRoll:
        assert expression == "1d20+2"
        return DiceRoll(expression, [9], 2, 11, 20, 1)

    monkeypatch.setattr("trpg_bot.rule_systems.dnd5e.roll_dice", fixed_roll)
    result = DND5ERuleSystem().check("察觉", {"character_name": "游侠", "skills": {"察觉": 2}}, args="DC12")
    assert result.dc == 12
    assert result.roll.modifier == 2
    assert result.success_level == "失败"


def test_rd_expression_with_modifier():
    assert parse_dice_expression("1d20+3") == (1, 20, 3)
