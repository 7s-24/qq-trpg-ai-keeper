from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from trpg_bot.config import get_settings
from trpg_bot.models import CampaignSettings


class CommandPermission(StrEnum):
    PLAYER = "player"
    KP = "kp"
    SUPERUSER = "superuser"

KP_COMMANDS = {
    ".模式", ".暂停", ".继续", ".等待", ".跳过", ".本轮结束", ".强制回复", ".清空本轮", ".规则", ".添加玩家", ".移除玩家", ".导入角色卡", ".修改角色卡",
}
SUPERUSER_COMMANDS = {".调试事件"}
PLAYER_COMMANDS = {
    ".r", ".ra", ".rd", ".检定", ".查看角色卡", ".当前状态", ".当前等待", ".当前发言", ".玩家列表", ".当前规则", ".角色卡模板", ".我的角色卡",
}


@dataclass(slots=True)
class UserContext:
    user_id: str
    group_id: str
    is_group_admin: bool = False


def is_superuser(user_id: str) -> bool:
    return user_id in get_settings().superusers


def is_kp(user: UserContext, settings: CampaignSettings) -> bool:
    return is_superuser(user.user_id) or user.user_id in settings.kp_users or user.is_group_admin


def required_permission(command: str) -> CommandPermission:
    if command in SUPERUSER_COMMANDS:
        return CommandPermission.SUPERUSER
    if command in KP_COMMANDS:
        return CommandPermission.KP
    return CommandPermission.PLAYER


def can_execute(command: str, user: UserContext, settings: CampaignSettings) -> bool:
    permission = required_permission(command)
    if permission == CommandPermission.SUPERUSER:
        return is_superuser(user.user_id)
    return permission == CommandPermission.PLAYER or is_kp(user, settings)


def deny_message(command: str) -> str:
    permission = required_permission(command)
    if permission == CommandPermission.SUPERUSER:
        return f"指令 {command} 只有机器人 superuser 可以使用。"
    if permission == CommandPermission.KP:
        return f"指令 {command} 只有 KP / 群管理员可以使用。"
    return "你没有权限执行该指令。"
