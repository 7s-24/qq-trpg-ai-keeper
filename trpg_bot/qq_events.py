from __future__ import annotations

import logging

from nonebot import get_driver, on_message, on_notice
from nonebot.adapters import Bot, Event
from nonebot.params import EventPlainText
from nonebot.rule import Rule

from trpg_bot.character_cards import CharacterCardStore, get_template
from trpg_bot.commands import parse_command
from trpg_bot.dice import DiceExpressionError, render_roll, roll_dice
from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.models import ReplyMode, RuleSystemName
from trpg_bot.permissions import UserContext, can_execute, deny_message
from trpg_bot.rule_systems import get_rule_system
from trpg_bot.turn_manager import TurnManager
from trpg_bot.utils import extract_mentioned_user_ids

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
    group_id = _get_group_id(event)
    user_id = _get_user_id(event)
    if not group_id or not user_id:
        return
    nickname = _get_nickname(event, user_id)
    command = parse_command(text)
    settings = turn_manager.get_settings(group_id)
    user = UserContext(user_id=user_id, group_id=group_id, is_group_admin=_is_admin(event))

    if command:
        if not can_execute(command.command, user, settings):
            await bot.send(event, deny_message(command.command))
            return
        reply = await dispatch_command(group_id, user_id, nickname, command.command, command.args)
        if reply:
            await bot.send(event, reply)
        return

    # 普通发言只进入回合缓冲区；绝不逐条调用 AI。
    if text.strip():
        turn_manager.buffer_message(group_id, user_id, nickname, text.strip())
        ai_reply = await turn_manager.maybe_auto_reply(group_id)
        if ai_reply and ai_reply.reply:
            await bot.send(event, ai_reply.reply)


async def dispatch_command(group_id: str, user_id: str, nickname: str, command: str, args: str) -> str:
    settings = turn_manager.get_settings(group_id)
    if command == ".模式":
        settings.reply_mode = ReplyMode.from_zh(args.strip())
        store.save_settings(settings)
        return f"已切换回复模式：{settings.reply_mode.zh()}"
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
        skill_args = args.strip()
        if not skill_args:
            return "请指定检定名称，例如：.ra 侦查 或 .检定 侦查。"
        parts = skill_args.split(maxsplit=1)
        name = parts[0]
        rest = parts[1] if len(parts) > 1 else skill_args
        rule = get_rule_system(settings.rule_system)
        card = card_store.load_card(settings.campaign_id, user_id)
        result = rule.check(name, card, args=rest)
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
            return "请使用 .添加玩家 @QQ号。当前适配器如无法解析 @，可输入 @123456。"
        for uid in users:
            turn_manager.add_player(group_id, uid)
        return "已添加玩家：" + "、".join(users)
    if command == ".移除玩家":
        users = extract_mentioned_user_ids(args)
        for uid in users:
            turn_manager.remove_player(group_id, uid)
        return "已移除玩家：" + ("、".join(users) if users else "无")
    if command == ".玩家列表":
        return "当前玩家：" + ("、".join(sorted(settings.active_players)) or "无")
    if command == ".等待":
        users = settings.active_players if args.strip() == "全员" else set(extract_mentioned_user_ids(args))
        settings = turn_manager.set_required(group_id, set(users))
        return "当前等待：" + ("、".join(sorted(settings.required_players or settings.active_players)) or "无")
    if command == ".跳过":
        users = set(extract_mentioned_user_ids(args))
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
        suffix = "" if not ai_reply.parse_error else f"\n（提示：AI 输出 JSON 解析失败，已保留原文：{ai_reply.parse_error}）"
        return ai_reply.reply + suffix
    if command == ".当前状态":
        return f"规则：{settings.rule_system.value}\n模式：{settings.reply_mode.zh()}\n回合：{settings.current_turn_id}\n玩家：{len(settings.active_players)} 人\n等待：{', '.join(sorted(settings.required_players or settings.active_players)) or '无'}"
    return "未知指令。"


@notice_handler.handle()
async def handle_notice(bot: Bot, event: Event) -> None:
    reply = await handle_poke_event(event)
    if reply:
        await bot.send(event, reply)


async def handle_poke_event(event: Event) -> str | None:
    """QQ 拍一拍事件降级接口：具体字段依赖 QQ 官方适配器版本，稳定替代是 .强制回复。"""
    # 第一版不写死事件结构，避免不同 QQ 事件能力导致误触发。
    return None


def _get_group_id(event: Event) -> str | None:
    data = getattr(event, "model_dump", lambda: {})()
    return str(data.get("group_id") or data.get("guild_id") or data.get("channel_id") or "") or None


def _get_user_id(event: Event) -> str | None:
    data = getattr(event, "model_dump", lambda: {})()
    user_id = data.get("user_id") or data.get("author", {}).get("id") or data.get("member", {}).get("user", {}).get("id")
    return str(user_id) if user_id else None


def _get_nickname(event: Event, fallback: str) -> str:
    data = getattr(event, "model_dump", lambda: {})()
    return str(data.get("nickname") or data.get("member", {}).get("nick") or data.get("author", {}).get("username") or fallback)


def _is_admin(event: Event) -> bool:
    data = getattr(event, "model_dump", lambda: {})()
    role = str(data.get("role") or data.get("member", {}).get("role") or data.get("member", {}).get("role_name") or "").lower()
    return role in {"admin", "administrator", "owner", "群主", "管理员"}
