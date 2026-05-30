from __future__ import annotations

import pytest

from trpg_bot.ai.prompts import build_user_prompt
from trpg_bot.models import DiceRoll
from trpg_bot.permissions import UserContext


@pytest.mark.asyncio
async def test_ra_buffers_check_message(isolated_core, monkeypatch):
    from trpg_bot.core_handler import handle_text

    monkeypatch.setattr("trpg_bot.rule_systems.coc7.roll_dice", lambda expression: DiceRoll(expression, [30], 0, 30, 100, 1))
    replies = await handle_text("g1", UserContext("u1", "g1"), "莉莉", ".ra 侦查")
    assert "侦查检定" in replies[0]
    messages = isolated_core.list_buffer("g1")
    assert messages[-1].message_type == "check"
    assert "已进行侦查检定" in messages[-1].content


@pytest.mark.asyncio
async def test_roll_buffers_dice_message(isolated_core, monkeypatch):
    from trpg_bot.core_handler import handle_text

    monkeypatch.setattr("trpg_bot.core_handler.roll_dice", lambda expression: DiceRoll(expression, [7], 0, 7, 20, 1))
    await handle_text("g1", UserContext("u1", "g1"), "莉莉", ".r 1d20")
    assert isolated_core.list_buffer("g1")[-1].message_type == "dice"


def test_build_user_prompt_separates_dice_outcomes(turn_manager):
    settings = turn_manager.get_settings("g1")
    turn_manager.buffer_message("g1", "u1", "莉莉", "我想翻找书架")
    turn_manager.buffer_message("g1", "u1", "莉莉", "莉莉(u1) 已进行侦查检定：技能值=50，骰点=30，结果=普通成功", message_type="check")
    prompt = build_user_prompt(settings, turn_manager.list_buffer("g1"), [], [])
    assert "'dice_outcomes':" in prompt
    assert "'turn_messages':" in prompt
    assert "已经发生的骰点/检定结果" in prompt

