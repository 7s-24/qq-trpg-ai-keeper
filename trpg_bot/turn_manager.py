from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any

from trpg_bot.ai.client import AIClient
from trpg_bot.character_cards import CharacterCardStore
from trpg_bot.memory.markdown_store import MarkdownStore
from trpg_bot.memory.retriever import MemoryRetriever
from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.models import AIReply, CampaignSettings, ReplyMode, TurnMessage

logger = logging.getLogger(__name__)


class TurnManager:
    def __init__(self, sqlite: SQLiteStore | None = None, ai: AIClient | None = None) -> None:
        self.sqlite = sqlite or SQLiteStore()
        self.markdown = MarkdownStore()
        self.retriever = MemoryRetriever(self.sqlite)
        self.cards = CharacterCardStore(self.sqlite)
        self.ai = ai or AIClient()
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def get_settings(self, group_id: str) -> CampaignSettings:
        return self.sqlite.get_or_create_settings(group_id)

    def buffer_message(self, group_id: str, user_id: str, nickname: str, content: str, message_type: str = "text") -> CampaignSettings:
        settings = self.get_settings(group_id)
        msg = TurnMessage(group_id, settings.campaign_id, settings.current_turn_id, user_id, nickname, content, message_type=message_type)
        self.sqlite.add_turn_message(msg)
        return settings

    def list_buffer(self, group_id: str) -> list[TurnMessage]:
        s = self.get_settings(group_id)
        return self.sqlite.list_turn_messages(s.campaign_id, s.current_turn_id)

    def render_buffer(self, group_id: str) -> str:
        messages = self.list_buffer(group_id)
        if not messages:
            return "当前回合还没有玩家发言。"
        grouped: dict[str, list[str]] = {}
        names: dict[str, str] = {}
        for msg in messages:
            grouped.setdefault(msg.user_id, []).append(msg.content)
            names[msg.user_id] = msg.nickname
        return "\n".join([f"- {names[user_id]}({user_id})：" + " / ".join(contents) for user_id, contents in grouped.items()])

    def clear_buffer(self, group_id: str) -> None:
        s = self.get_settings(group_id)
        self.sqlite.clear_turn_messages(s.campaign_id, s.current_turn_id)

    def has_all_required_spoken(self, settings: CampaignSettings) -> bool:
        required = settings.required_players or settings.active_players
        if not required:
            return False
        spoken = {m.user_id for m in self.sqlite.list_turn_messages(settings.campaign_id, settings.current_turn_id)}
        return required.issubset(spoken)

    def should_auto_reply(self, settings: CampaignSettings) -> bool:
        return settings.reply_mode in {ReplyMode.AUTO, ReplyMode.HYBRID} and self.has_all_required_spoken(settings)

    async def maybe_auto_reply(self, group_id: str) -> AIReply | None:
        settings = self.get_settings(group_id)
        if not self.should_auto_reply(settings):
            return None
        return await self.finalize_turn(group_id, force=False)

    async def finalize_turn(self, group_id: str, force: bool = True) -> AIReply:
        async with self._locks[group_id]:
            settings = self.get_settings(group_id)
            if not force and not self.should_auto_reply(settings):
                return AIReply(reply="当前还未满足自动回复条件。", memory_update={}, next_turn_required_players=[])
            messages = self.sqlite.list_turn_messages(settings.campaign_id, settings.current_turn_id)
            if not messages:
                return AIReply(reply="当前回合没有可结算的玩家发言。", memory_update={}, next_turn_required_players=[])
            memories = self.retriever.retrieve(settings.campaign_id, [m.content for m in messages])
            character_summaries = [self.cards.render_card_summary(settings.campaign_id, uid) for uid in sorted({m.user_id for m in messages})]
            try:
                ai_reply = await self.ai.generate_reply(settings, messages, memories, character_summaries)
            except Exception as exc:
                logger.exception("AI turn finalization failed for campaign %s turn %s", settings.campaign_id, settings.current_turn_id)
                return AIReply(
                    reply=f"AI 结算失败：{exc}。当前回合发言已保留，请稍后重试 .强制回复 或检查 AI 配置。",
                    memory_update={},
                    next_turn_required_players=[],
                    parse_error=str(exc),
                )
            rendered_reply = self.render_ai_reply(settings, messages, ai_reply)
            ai_reply.reply = rendered_reply
            self.markdown.append_session_reply(settings.campaign_id, settings.current_turn_id, messages, rendered_reply)
            self.markdown.append_memory_update(settings.campaign_id, settings.current_turn_id, ai_reply.memory_update)
            self._write_structured_memories(settings, ai_reply)
            settings.required_players = set(ai_reply.next_turn_required_players)
            self.sqlite.close_and_next_turn(settings)
            return ai_reply

    def render_ai_reply(self, settings: CampaignSettings, messages: list[TurnMessage], ai_reply: AIReply) -> str:
        if not ai_reply.dice_requests:
            return ai_reply.reply
        names = {m.user_id: m.nickname for m in messages}
        lines = [ai_reply.reply.rstrip(), "", "🎲 需要检定:"]
        for request in ai_reply.dice_requests:
            label = names.get(request.user_id) or self._card_display_name(settings.campaign_id, request.user_id) or request.user_id
            reason = f"（用于：{request.reason}）" if request.reason else ""
            lines.append(f"- {label}({request.user_id})：请发送 {request.suggested_command}{reason}")
        return "\n".join(lines).strip()

    def _card_display_name(self, campaign_id: str, user_id: str) -> str | None:
        card = self.cards.load_card(campaign_id, user_id)
        if not card:
            return None
        return str(card.get("character_name") or card.get("player") or "") or None

    def _write_structured_memories(self, settings: CampaignSettings, ai_reply: AIReply) -> None:
        type_map = {"session_log": "event", "characters": "character", "npcs": "npc", "locations": "location", "clues": "clue", "world_state": "world_state", "unresolved_threads": "thread"}
        for key, items in ai_reply.memory_update.items():
            for item in items:
                title, content, tags = _memory_fields(item)
                self.sqlite.upsert_memory(settings.campaign_id, type_map.get(key, key), title, content, tags, settings.current_turn_id)

    def set_running(self, group_id: str, running: bool) -> CampaignSettings:
        s = self.get_settings(group_id)
        s.running = running
        self.sqlite.save_settings(s)
        return s

    def add_player(self, group_id: str, user_id: str) -> CampaignSettings:
        s = self.get_settings(group_id)
        s.active_players.add(user_id)
        self.sqlite.save_settings(s)
        return s

    def remove_player(self, group_id: str, user_id: str) -> CampaignSettings:
        s = self.get_settings(group_id)
        s.active_players.discard(user_id)
        s.required_players.discard(user_id)
        self.sqlite.save_settings(s)
        return s

    def set_required(self, group_id: str, users: set[str]) -> CampaignSettings:
        s = self.get_settings(group_id)
        s.required_players = set(users)
        self.sqlite.save_settings(s)
        return s

    def skip_players(self, group_id: str, users: set[str]) -> CampaignSettings:
        s = self.get_settings(group_id)
        s.required_players.difference_update(users)
        self.sqlite.save_settings(s)
        return s


def _memory_fields(item: Any) -> tuple[str, str, list[str]]:
    if isinstance(item, dict):
        return str(item.get("title") or item.get("name") or "未命名记忆"), str(item.get("content") or item), [str(t) for t in item.get("tags", [])] if isinstance(item.get("tags"), list) else []
    text = str(item)
    return text[:40] or "记忆", text, []
