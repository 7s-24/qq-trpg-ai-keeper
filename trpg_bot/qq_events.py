from __future__ import annotations

from typing import Any

from nonebot import get_driver, on_message, on_notice
from nonebot.adapters import Bot, Event
from nonebot.params import EventPlainText
from nonebot.rule import Rule

from trpg_bot.commands import parse_command
from trpg_bot.core_handler import _write_debug_event, dispatch_command, handle_text, store
from trpg_bot.permissions import UserContext, deny_message, is_superuser


@get_driver().on_startup
def _startup() -> None:
    store.init_db()


async def _always() -> bool:
    return True


message_handler = on_message(rule=Rule(_always), priority=10, block=False)
notice_handler = on_notice(priority=10, block=False)


@message_handler.handle()
async def handle_group_message(bot: Bot, event: Event, text: str = EventPlainText()) -> None:
    event_dump = _event_dump(event)
    group_id = _get_group_id_from_dump(event_dump)
    user_id = _get_user_id_from_dump(event_dump)
    command = parse_command(text)

    # .调试事件 用于排查真实 QQ 字段；即使 group_id 解析失败，也允许 superuser 写入原始 event。
    if command and command.command == ".调试事件":
        if not user_id or not is_superuser(user_id):
            await bot.send(event, deny_message(command.command))
            return
        await bot.send(event, _write_debug_event(group_id or "unknown", user_id, event_dump))
        return

    if not group_id or not user_id:
        return
    nickname = _get_nickname_from_dump(event_dump, user_id)
    user = UserContext(user_id=user_id, group_id=group_id, is_group_admin=_is_admin_from_dump(event_dump))
    for reply in await handle_text(group_id, user, nickname, text, event_dump=event_dump):
        await bot.send(event, reply)


@notice_handler.handle()
async def handle_notice(bot: Bot, event: Event) -> None:
    reply = await handle_poke_event(event)
    if reply:
        await bot.send(event, reply)


async def handle_poke_event(event: Event) -> str | None:
    """QQ 拍一拍事件降级接口：具体字段依赖 QQ 官方适配器版本，稳定替代是 .强制回复。"""
    return None


def _event_dump(event: Event) -> dict[str, Any]:
    try:
        data = getattr(event, "model_dump", lambda: {})()
    except Exception as exc:  # pragma: no cover - defensive against adapter-specific dump failures
        return {"dump_error": repr(exc)}
    return data if isinstance(data, dict) else {"raw": str(data)}


def _get_group_id_from_dump(data: dict[str, Any]) -> str | None:
    return str(data.get("group_id") or data.get("guild_id") or data.get("channel_id") or "") or None


def _get_user_id_from_dump(data: dict[str, Any]) -> str | None:
    user_id = data.get("user_id") or data.get("author", {}).get("id") or data.get("member", {}).get("user", {}).get("id")
    return str(user_id) if user_id else None


def _get_nickname_from_dump(data: dict[str, Any], fallback: str) -> str:
    return str(data.get("nickname") or data.get("member", {}).get("nick") or data.get("author", {}).get("username") or fallback)


def _is_admin_from_dump(data: dict[str, Any]) -> bool:
    role = str(data.get("role") or data.get("member", {}).get("role") or data.get("member", {}).get("role_name") or "").lower()
    return role in {"admin", "administrator", "owner", "群主", "管理员"}
