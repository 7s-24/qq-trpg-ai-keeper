from __future__ import annotations

import pytest

from trpg_bot.models import ReplyMode
from trpg_bot.permissions import UserContext


@pytest.mark.asyncio
async def test_handle_text_buffers_plain_message(isolated_core):
    from trpg_bot.core_handler import handle_text

    replies = await handle_text("g1", UserContext("u1", "g1"), "莉莉", "我调查房间")
    assert replies == []
    assert "我调查房间" in isolated_core.render_buffer("g1")


@pytest.mark.asyncio
async def test_handle_text_dispatches_player_command(isolated_core):
    from trpg_bot.core_handler import handle_text

    replies = await handle_text("g1", UserContext("u1", "g1"), "莉莉", ".帮助 骰点")
    assert replies and ".r 1d100" in replies[0]


@pytest.mark.asyncio
async def test_handle_text_denies_kp_command_for_player(isolated_core):
    from trpg_bot.core_handler import handle_text

    replies = await handle_text("g1", UserContext("u1", "g1"), "莉莉", ".强制回复")
    assert "只有 KP" in replies[0]


@pytest.mark.asyncio
async def test_handle_text_admin_can_change_mode(isolated_core):
    from trpg_bot.core_handler import handle_text

    replies = await handle_text("g1", UserContext("admin", "g1", is_group_admin=True), "KP", ".模式 自动")
    assert "自动" in replies[0]
    assert isolated_core.get_settings("g1").reply_mode == ReplyMode.AUTO

