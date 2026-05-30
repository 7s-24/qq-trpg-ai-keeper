from __future__ import annotations

import asyncio
import json

import httpx

from trpg_bot.ai.client import AIClient
from trpg_bot.core_handler import dispatch_command
from trpg_bot.models import RuleSystemName
from trpg_bot.turn_manager import TurnManager


def test_mock_ai_success_writes_memory_markdown_and_payload(temp_settings, temp_store, mock_ai_client):
    content = {
        "reply": "你们找到一枚铜钥匙。",
        "memory_update": {"session_log": [{"title": "铜钥匙", "content": "玩家在书架后找到铜钥匙。", "tags": ["线索"]}]},
        "next_turn": {"required_players": ["u2"], "reason": "等待回应"},
        "dice_requests": [{"user_id": "u1", "skill": "侦查", "reason": "继续搜索"}],
    }
    ai, captured = mock_ai_client(content)
    manager = TurnManager(temp_store, ai=ai)
    settings = manager.get_settings("g1")
    settings.rule_system = RuleSystemName.COC7
    temp_store.save_settings(settings)
    manager.buffer_message("g1", "u1", "莉莉", "我检查书架")
    manager.buffer_message("g1", "u1", "莉莉", "莉莉(u1) 已进行侦查检定：技能值=50，骰点=30，结果=普通成功", message_type="check")

    reply = asyncio.run(manager.finalize_turn("g1", force=True))

    assert "铜钥匙" in reply.reply
    assert "请发送 .ra 侦查" in reply.reply
    assert manager.get_settings("g1").current_turn_id == 2
    assert manager.get_settings("g1").required_players == {"u2"}
    assert "dice_outcomes" in captured["payload"]["messages"][1]["content"]
    assert "已进行侦查检定" in captured["payload"]["messages"][1]["content"]
    log = temp_settings.data_dir / "campaigns" / "group_g1" / "session_logs" / "turn_0001.md"
    assert log.exists()
    assert "铜钥匙" in log.read_text(encoding="utf-8")
    with temp_store.connect() as conn:
        row = conn.execute("SELECT title, content FROM memories WHERE campaign_id='group_g1'").fetchone()
    assert row["title"] == "铜钥匙"


def test_dirty_json_fallback_and_non_json_parse_error(temp_settings, temp_store, mock_ai_client, monkeypatch):
    wrapped = '前缀文字 {"reply":"仍然解析","memory_update":{},"next_turn":{"required_players":[]},"dice_requests":[]} 后缀'
    ai, _ = mock_ai_client(wrapped)
    parsed = asyncio.run(ai.generate_reply(temp_store.get_or_create_settings("g1"), [], [], []))
    assert parsed.reply == "仍然解析"
    assert parsed.parse_error is None

    ai, _ = mock_ai_client("这不是 JSON")
    manager = TurnManager(temp_store, ai=ai)
    manager.buffer_message("g1", "u1", "莉莉", "我开门")

    import trpg_bot.core_handler as core

    monkeypatch.setattr(core, "turn_manager", manager)
    monkeypatch.setattr(core, "store", temp_store)
    reply = asyncio.run(dispatch_command("g1", "kp", "KP", ".本轮结束", ""))
    assert "这不是 JSON" in reply
    assert "未找到 JSON 对象" in reply
    assert manager.get_settings("g1").current_turn_id == 2


def test_mock_ai_timeout_keeps_turn_and_buffer(temp_settings, temp_store, mock_ai_client):
    timeout = httpx.TimeoutException("timeout")
    ai, _ = mock_ai_client("{}", exc=timeout)
    manager = TurnManager(temp_store, ai=ai)
    manager.buffer_message("g1", "u1", "莉莉", "我开门")
    before = manager.get_settings("g1").current_turn_id
    reply = asyncio.run(manager.finalize_turn("g1", force=True))
    assert "AI 结算失败" in reply.reply
    assert manager.get_settings("g1").current_turn_id == before
    assert "我开门" in manager.render_buffer("g1")


def test_mock_ai_http_error_keeps_turn_and_buffer(temp_settings, temp_store):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "bad"}, request=request)

    temp_settings.ai_api_key = "test-key"
    manager = TurnManager(temp_store, ai=AIClient(transport=httpx.MockTransport(handler)))
    manager.buffer_message("g1", "u1", "莉莉", "我开门")
    before = manager.get_settings("g1").current_turn_id
    reply = asyncio.run(manager.finalize_turn("g1", force=True))
    assert "AI 结算失败" in reply.reply
    assert manager.get_settings("g1").current_turn_id == before

