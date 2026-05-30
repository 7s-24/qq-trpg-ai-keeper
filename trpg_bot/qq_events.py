from __future__ import annotations

import json
import logging
from typing import Any

from nonebot import get_driver, on_message, on_notice
from nonebot.adapters import Bot, Event
from nonebot.params import EventPlainText
from nonebot.rule import Rule

from trpg_bot.character_cards import CharacterCardStore, get_template
from trpg_bot.commands import parse_check_command_args, parse_command
from trpg_bot.config import get_settings
from trpg_bot.dice import DiceExpressionError, render_roll, roll_dice
from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.models import ReplyMode, RuleSystemName
from trpg_bot.permissions import UserContext, can_execute, deny_message, is_superuser
from trpg_bot.rule_systems import get_rule_system
from trpg_bot.turn_manager import TurnManager
from trpg_bot.utils import extract_mentioned_user_ids, now_iso

logger = logging.getLogger(__name__)
store = SQLiteStore()
turn_manager = TurnManager(store)
card_store = CharacterCardStore(store)


@get_driver().on_startup
def _startup() -> None:
    store.init_db()
    logger.info("TRPG QQ bot initialized")


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

    # .调试事件 的目的就是排查真实 QQ 字段；即使 group_id 解析失败，也允许 superuser 写入原始 event。
    if command and command.command == ".调试事件":
        if not user_id or not is_superuser(user_id):
            await bot.send(event, deny_message(command.command))
            return
        await bot.send(event, _write_debug_event(group_id or "unknown", user_id, event_dump))
        return

    if not group_id or not user_id:
        return
    nickname = _get_nickname_from_dump(event_dump, user_id)
    settings = turn_manager.get_settings(group_id)
    user = UserContext(user_id=user_id, group_id=group_id, is_group_admin=_is_admin_from_dump(event_dump))

    if command:
        if not can_execute(command.command, user, settings):
            await bot.send(event, deny_message(command.command))
            return
        try:
            reply = await dispatch_command(
                group_id,
                user_id,
                nickname,
                command.command,
                command.args,
                event_dump=event_dump,
            )
        except ValueError as exc:
            reply = f"参数错误：{exc}"
        if reply:
            await bot.send(event, reply)
        return

    # 暂停时普通发言不进入回合缓冲区；指令、骰点和管理操作仍可用。
    if not settings.running:
        return

    # 普通发言只进入回合缓冲区；绝不逐条调用 AI。
    if text.strip():
        turn_manager.buffer_message(group_id, user_id, nickname, text.strip())
        ai_reply = await turn_manager.maybe_auto_reply(group_id)
        if ai_reply and ai_reply.reply:
            await bot.send(event, ai_reply.reply)


async def dispatch_command(
    group_id: str,
    user_id: str,
    nickname: str,
    command: str,
    args: str,
    event_dump: dict[str, Any] | None = None,
) -> str:
    settings = turn_manager.get_settings(group_id)
    try:
        if command == ".模式":
            settings.reply_mode = ReplyMode.from_zh(args.strip())
            store.save_settings(settings)
            return f"已切换回复模式：{settings.reply_mode.zh()}"
        if command == ".暂停":
            turn_manager.set_running(group_id, False)
            return "已暂停跑团记录：普通群消息不会进入本轮缓冲区；骰点和管理指令仍可用。"
        if command == ".继续":
            turn_manager.set_running(group_id, True)
            return "已继续跑团记录：普通群消息会进入本轮缓冲区。"
        if command == ".调试事件":
            return _write_debug_event(group_id, user_id, event_dump or {})
        if command == ".规则":
            settings.rule_system = RuleSystemName.from_command(args.strip())
            store.save_settings(settings)
            return f"已切换规则系统：{settings.rule_system.value}"
        if command == ".当前规则":
            return f"当前规则：{settings.rule_system.value}"
        if command in {".r", ".rd"}:
            try:
                return render_roll(roll_dice(args.strip() or ("1d20" if command == ".rd" else "1d100")))
            except DiceExpressionError as exc:
                return str(exc)
        if command in {".ra", ".检定"}:
            parsed = parse_check_command_args(command, args)
            rule = get_rule_system(settings.rule_system)
            card = card_store.load_card(settings.campaign_id, user_id)
            result = rule.check(parsed.name, card, args=parsed.rest)
            return rule.render_check_result(result)
        if command == ".角色卡模板":
            system = RuleSystemName.from_command(args.strip()) if args.strip() else settings.rule_system
            return get_template(system)
        if command == ".导入角色卡":
            ok, msg = card_store.import_yaml(settings.campaign_id, user_id, args)
            return msg if ok else "导入失败：" + msg
        if command in {".我的角色卡", ".查看角色卡"}:
            target = (extract_mentioned_user_ids(args) or [user_id])[0]
            return card_store.render_card_summary(settings.campaign_id, target)
        if command == ".添加玩家":
            users = extract_mentioned_user_ids(args)
            if not users:
                raise ValueError("请使用 .添加玩家 @QQ号。当前适配器如无法解析 @，可输入 @123456。")
            for uid in users:
                turn_manager.add_player(group_id, uid)
            return "已添加玩家：" + "、".join(users)
        if command == ".移除玩家":
            users = extract_mentioned_user_ids(args)
            if not users:
                raise ValueError("请使用 .移除玩家 @QQ号。")
            for uid in users:
                turn_manager.remove_player(group_id, uid)
            return "已移除玩家：" + "、".join(users)
        if command == ".玩家列表":
            return "当前玩家：" + ("、".join(sorted(settings.active_players)) or "无")
        if command == ".等待":
            if args.strip() == "全员":
                users = settings.active_players
            else:
                users = set(extract_mentioned_user_ids(args))
                if not users:
                    raise ValueError("请使用 .等待 @玩家1 @玩家2，或 .等待 全员。")
            settings = turn_manager.set_required(group_id, set(users))
            return "当前等待：" + ("、".join(sorted(settings.required_players or settings.active_players)) or "无")
        if command == ".跳过":
            users = set(extract_mentioned_user_ids(args))
            if not users:
                raise ValueError("请使用 .跳过 @玩家。")
            settings = turn_manager.skip_players(group_id, users)
            return "已跳过；当前等待：" + ("、".join(sorted(settings.required_players or settings.active_players)) or "无")
        if command == ".当前等待":
            return "当前等待：" + ("、".join(sorted(settings.required_players or settings.active_players)) or "无")
        if command == ".当前发言":
            return turn_manager.render_buffer(group_id)
        if command == ".清空本轮":
            turn_manager.clear_buffer(group_id)
            return "已清空当前回合缓冲区。"
        if command in {".本轮结束", ".强制回复"}:
            ai_reply = await turn_manager.finalize_turn(group_id, force=True)
            suffix = "" if not ai_reply.parse_error else f"\n（提示：AI 结算或 JSON 解析异常，当前缓冲区仅在成功结算后进入下一轮：{ai_reply.parse_error}）"
            return ai_reply.reply + suffix
        if command == ".当前状态":
            running = "运行中" if settings.running else "已暂停"
            return f"状态：{running}\n规则：{settings.rule_system.value}\n模式：{settings.reply_mode.zh()}\n回合：{settings.current_turn_id}\n玩家：{len(settings.active_players)} 人\n等待：{', '.join(sorted(settings.required_players or settings.active_players)) or '无'}"
        return "未知指令。"
    except ValueError as exc:
        return f"参数错误：{exc}"


@notice_handler.handle()
async def handle_notice(bot: Bot, event: Event) -> None:
    reply = await handle_poke_event(event)
    if reply:
        await bot.send(event, reply)


async def handle_poke_event(event: Event) -> str | None:
    """QQ 拍一拍事件降级接口：具体字段依赖 QQ 官方适配器版本，稳定替代是 .强制回复。"""
    # 第一版不写死事件结构，避免不同 QQ 事件能力导致误触发。
    return None


def _write_debug_event(group_id: str, user_id: str, event_dump: dict[str, Any]) -> str:
    log_dir = get_settings().data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "qq_event_debug.jsonl"
    record = {"timestamp": now_iso(), "group_id": group_id, "user_id": user_id, "event": event_dump}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return f"已写入事件调试日志：{path}"


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


def _get_group_id(event: Event) -> str | None:
    return _get_group_id_from_dump(_event_dump(event))


def _get_user_id(event: Event) -> str | None:
    return _get_user_id_from_dump(_event_dump(event))


def _get_nickname(event: Event, fallback: str) -> str:
    return _get_nickname_from_dump(_event_dump(event), fallback)


def _is_admin(event: Event) -> bool:
    return _is_admin_from_dump(_event_dump(event))
