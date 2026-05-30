from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal


class ReplyMode(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    HYBRID = "hybrid"

    @classmethod
    def from_zh(cls, value: str) -> "ReplyMode":
        mapping = {"自动": cls.AUTO, "手动": cls.MANUAL, "混合": cls.HYBRID}
        if value.lower() in {m.value for m in cls}:
            return cls(value.lower())
        if value not in mapping:
            raise ValueError("模式必须是：自动、手动、混合")
        return mapping[value]

    def zh(self) -> str:
        return {self.AUTO: "自动", self.MANUAL: "手动", self.HYBRID: "混合"}[self]


class RuleSystemName(StrEnum):
    COC7 = "COC7"
    DND5E = "DND5E"
    CUSTOM = "CUSTOM"

    @classmethod
    def from_command(cls, value: str) -> "RuleSystemName":
        normalized = value.strip().upper()
        mapping = {"COC": cls.COC7, "COC7": cls.COC7, "DND": cls.DND5E, "DND5E": cls.DND5E, "自定义": cls.CUSTOM, "CUSTOM": cls.CUSTOM}
        if normalized in mapping:
            return mapping[normalized]
        if value.strip() in mapping:
            return mapping[value.strip()]
        raise ValueError("规则必须是：COC、DND、自定义")


@dataclass(slots=True)
class TurnMessage:
    group_id: str
    campaign_id: str
    turn_id: int
    user_id: str
    nickname: str
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_type: str = "text"


@dataclass(slots=True)
class CampaignSettings:
    campaign_id: str
    group_id: str
    reply_mode: ReplyMode = ReplyMode.MANUAL
    rule_system: RuleSystemName = RuleSystemName.COC7
    active_players: set[str] = field(default_factory=set)
    required_players: set[str] = field(default_factory=set)
    kp_users: set[str] = field(default_factory=set)
    current_turn_id: int = 1


@dataclass(slots=True)
class DiceRoll:
    expression: str
    dice: list[int]
    modifier: int
    total: int
    sides: int
    count: int


@dataclass(slots=True)
class CheckResult:
    system: str
    name: str
    character_name: str
    roll: DiceRoll
    target: int | None
    dc: int | None
    success_level: str
    success: bool
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AIReply:
    reply: str
    memory_update: dict[str, list[Any]]
    next_turn_required_players: list[str]
    next_turn_reason: str = ""
    dice_requests: list[Any] = field(default_factory=list)
    raw_text: str = ""
    parse_error: str | None = None


PermissionLevel = Literal["player", "kp"]
