from __future__ import annotations

import json

from trpg_bot.ai.output_parser import parse_ai_output
from trpg_bot.models import AIReply, DiceRequest, RuleSystemName


def test_parse_dice_requests_fills_missing_fields():
    reply = parse_ai_output(
        json.dumps(
            {
                "reply": "门锁看起来需要处理。",
                "memory_update": {},
                "next_turn": {"required_players": ["123"]},
                "dice_requests": [{"user_id": "123", "reason": "撬开门锁"}],
            },
            ensure_ascii=False,
        ),
        RuleSystemName.COC7,
    )
    assert reply.dice_requests == [DiceRequest(user_id="123", skill="撬开门锁", reason="撬开门锁", suggested_command=".ra 撬开门锁")]


def test_render_dice_requests_with_copyable_command(turn_manager):
    settings = turn_manager.get_settings("g1")
    turn_manager.buffer_message("g1", "123", "莉莉", "我想仔细观察房间")
    messages = turn_manager.list_buffer("g1")
    ai_reply = AIReply(
        reply="你可以先观察一下。",
        memory_update={},
        next_turn_required_players=[],
        dice_requests=[DiceRequest(user_id="123", skill="侦查", reason="仔细观察房间", suggested_command=".ra 侦查")],
    )
    rendered = turn_manager.render_ai_reply(settings, messages, ai_reply)
    assert "🎲 需要检定" in rendered
    assert "莉莉(123)：请发送 .ra 侦查" in rendered
    assert "用于：仔细观察房间" in rendered


def test_dnd_default_suggested_command_mentions_dc():
    reply = parse_ai_output(
        '{"reply":"roll","dice_requests":[{"user_id":"1","skill":"察觉"}]}',
        RuleSystemName.DND5E,
    )
    assert reply.dice_requests[0].suggested_command == ".检定 察觉 DC?"

