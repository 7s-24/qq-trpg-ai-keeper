from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trpg_bot.config import get_settings
from trpg_bot.models import CampaignSettings


class CommandPermission(StrEnum):
    PLAYER = "player"
    KP = "kp"

KP_COMMANDS = {
    ".模式", ".等待", ".跳过", ".本轮结束", ".强制回复", ".清空本轮", ".规则", ".添加玩家", ".移除玩家", ".导入角色卡", ".修改角色卡",
}
PLAYER_COMMANDS = {
    ".r", ".ra", ".rd", ".检定", ".查看角色卡", ".当前状态", ".当前等待", ".当前发言", ".玩家列表", ".当前规则", ".角色卡模板", ".我的角色卡",
}


@dataclass(slots=True)
class UserContext:
    user_id: str
    group_id: str
    is_group_admin: bool = False


def is_kp(user: UserContext, settings: CampaignSettings) -> bool:
    app_settings = get_settings()
    return user.user_id in app_settings.superusers or user.user_id in settings.kp_users or user.is_group_admin


def required_permission(command: str) -> CommandPermission:
    if command in KP_COMMANDS:
        return CommandPermission.KP
    return CommandPermission.PLAYER


def can_execute(command: str, user: UserContext, settings: CampaignSettings) -> bool:
    permission = required_permission(command)
    return permission == CommandPermission.PLAYER or is_kp(user, settings)


def deny_message(command: str) -> str:
    if required_permission(command) == CommandPermission.KP:
        return f"指令 {command} 只有 KP / 群管理员可以使用。"
    return "你没有权限执行该指令。"
