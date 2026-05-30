from __future__ import annotations

import logging
from typing import Any


from trpg_bot.ai.output_parser import parse_ai_output
from trpg_bot.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from trpg_bot.config import get_settings
from trpg_bot.models import AIReply, CampaignSettings, TurnMessage

logger = logging.getLogger(__name__)


class AIClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def generate_reply(self, campaign_settings: CampaignSettings, messages: list[TurnMessage], memories: list[dict[str, Any]], character_summaries: list[str]) -> AIReply:
        if not self.settings.ai_api_key:
            logger.warning("TRPG_AI_API_KEY not configured; using local fallback reply")
            fallback = {
                "reply": "【本地占位回复】已记录本轮发言。请配置 TRPG_AI_API_KEY 后启用 AI KP 回复。",
                "memory_update": {"session_log": ["本轮使用本地占位回复，未调用 AI。"], "characters": [], "npcs": [], "locations": [], "clues": [], "world_state": [], "unresolved_threads": []},
                "next_turn": {"required_players": [], "reason": "未配置 AI"},
                "dice_requests": [],
            }
            return parse_ai_output(__import__("json").dumps(fallback, ensure_ascii=False))
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
        import httpx

        async with httpx.AsyncClient(timeout=self.settings.ai_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        content = data["choices"][0]["message"]["content"]
        return parse_ai_output(content)
