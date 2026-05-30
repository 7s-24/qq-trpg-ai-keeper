from __future__ import annotations

import pytest

from trpg_bot.models import DiceRoll
from trpg_bot.rule_systems.coc7 import COC7RuleSystem


def test_coc7_alias_observation_resolves_to_spot_hidden(monkeypatch):
    monkeypatch.setattr("trpg_bot.rule_systems.coc7.roll_dice", lambda expression: DiceRoll(expression, [40], 0, 40, 100, 1))
    result = COC7RuleSystem().check("观察", {"character_name": "莉莉", "skills": {"侦查": 60}})
    reply = COC7RuleSystem().render_check_result(result)
    assert result.name == "侦查"
    assert result.target == 60
    assert result.success
    assert "按『侦查』判定" in reply


def test_coc7_unknown_skill_suggests_candidates(monkeypatch):
    monkeypatch.setattr("trpg_bot.rule_systems.coc7.roll_dice", lambda expression: DiceRoll(expression, [40], 0, 40, 100, 1))
    result = COC7RuleSystem().check("星舰驾驶", {"character_name": "莉莉", "skills": {"侦查": 60}})
    reply = COC7RuleSystem().render_check_result(result)
    assert "未找到技能『星舰驾驶』" in reply
    assert "你是不是想检定" in reply


def test_coc7_no_card_uses_default_value(monkeypatch):
    monkeypatch.setattr("trpg_bot.rule_systems.coc7.roll_dice", lambda expression: DiceRoll(expression, [40], 0, 40, 100, 1))
    result = COC7RuleSystem().check("侦查", None)
    reply = COC7RuleSystem().render_check_result(result)
    assert result.target == 50
    assert result.detail["used_default"] is True
    assert "使用默认值 50" in reply
