from __future__ import annotations

import pytest

from trpg_bot.permissions import UserContext, can_execute


@pytest.mark.asyncio
@pytest.mark.parametrize("command, expected", [
    (".帮助", ".ra 侦查"),
    (".帮助 骰点", ".r 1d100"),
    (".帮助 检定", ".检定 力量 DC15"),
    (".帮助 角色卡", ".生成角色卡"),
    (".帮助 管理", ".本轮结束"),
])
async def test_help_topics_return_examples(isolated_core, command, expected):
    from trpg_bot.core_handler import handle_text

    replies = await handle_text("g1", UserContext("u1", "g1"), "莉莉", command)
    assert replies
    assert expected in replies[0]


def test_help_and_generate_card_are_player_commands():
    assert can_execute(".帮助", UserContext("u1", "g1"), isolated_settings())
    assert can_execute(".生成角色卡", UserContext("u1", "g1"), isolated_settings())


def isolated_settings():
    from trpg_bot.models import CampaignSettings

    return CampaignSettings("c", "g1")

