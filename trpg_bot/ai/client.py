from __future__ import annotations

import logging
from typing import Any

import httpx

from trpg_bot.ai.output_parser import parse_ai_output
from trpg_bot.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from trpg_bot.config import get_settings
from trpg_bot.models import AIReply, CampaignSettings, TurnMessage

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self, client: httpx.AsyncClient | None = None, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = get_settings()
        self._client = client
        self._transport = transport

    async def generate_reply(self, campaign_settings: CampaignSettings, messages: list[TurnMessage], memories: list[dict[str, Any]], character_summaries: list[str]) -> AIReply:
        if not self.settings.ai_api_key:
            logger.warning("TRPG_AI_API_KEY not configured; using local fallback reply")
            fallback = {
                "reply": "【本地占位回复】已记录本轮发言。请配置 TRPG_AI_API_KEY 后启用 AI KP 回复。",
                "memory_update": {"session_log": ["本轮使用本地占位回复，未调用 AI。"], "characters": [], "npcs": [], "locations": [], "clues": [], "world_state": [], "unresolved_threads": []},
                "next_turn": {"required_players": [], "reason": "未配置 AI"},
                "dice_requests": [],
            }
            return parse_ai_output(__import__("json").dumps(fallback, ensure_ascii=False), campaign_settings.rule_system)
        url = self.settings.ai_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.ai_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(campaign_settings, messages, memories, character_summaries)},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.settings.ai_api_key}", "Content-Type": "application/json"}
        if self._client is not None:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        else:
            async with httpx.AsyncClient(timeout=self.settings.ai_timeout_seconds, transport=self._transport) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        content = data["choices"][0]["message"]["content"]
        return parse_ai_output(content, campaign_settings.rule_system)

    async def generate_character_card_yaml(self, rule_system: str, description: str, template: str) -> str | None:
        if not self.settings.ai_api_key:
            return None
        url = self.settings.ai_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.ai_model,
            "messages": [
                {"role": "system", "content": "你是跑团角色卡助手。只输出一份 YAML，不要 Markdown 代码块，不要解释。"},
                {"role": "user", "content": f"规则系统：{rule_system}\n玩家描述：{description}\n请按这个模板补全合法角色卡：\n{template}"},
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.ai_api_key}", "Content-Type": "application/json"}
        if self._client is not None:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        else:
            async with httpx.AsyncClient(timeout=self.settings.ai_timeout_seconds, transport=self._transport) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        return str(data["choices"][0]["message"]["content"]).strip()
