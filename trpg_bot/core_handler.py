from __future__ import annotations

import json
import logging
from typing import Any

from trpg_bot.character_cards import CharacterCardStore, get_template
from trpg_bot.commands import parse_check_command_args, parse_command
from trpg_bot.config import get_settings
from trpg_bot.dice import DiceExpressionError, render_roll, roll_dice
from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.models import CheckResult, DiceRoll, ReplyMode, RuleSystemName
from trpg_bot.permissions import UserContext, can_execute, deny_message
from trpg_bot.rule_systems import get_rule_system
from trpg_bot.turn_manager import TurnManager
from trpg_bot.utils import extract_mentioned_user_ids, now_iso

logger = logging.getLogger(__name__)
store = SQLiteStore()
turn_manager = TurnManager(store)
card_store = CharacterCardStore(store)


async def handle_text(group_id: str, user: UserContext, nickname: str, text: str, event_dump: dict[str, Any] | None = None) -> list[str]:
    command = parse_command(text)
    settings = turn_manager.get_settings(group_id)
    if command:
        if not can_execute(command.command, user, settings):
            return [deny_message(command.command)]
        reply = await dispatch_command(group_id, user.user_id, nickname, command.command, command.args, event_dump=event_dump)
        return [reply] if reply else []
    if not settings.running:
        return []
    if not text.strip():
        return []
    turn_manager.buffer_message(group_id, user.user_id, nickname, text.strip())
    ai_reply = await turn_manager.maybe_auto_reply(group_id)
    return [ai_reply.reply] if ai_reply and ai_reply.reply else []


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
        if command == ".帮助":
            return help_text(args)
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
            expression = args.strip() or ("1d20" if command == ".rd" else "1d100")
            try:
                roll = roll_dice(expression)
            except DiceExpressionError as exc:
                return str(exc)
            reply = render_roll(roll)
            turn_manager.buffer_message(group_id, user_id, nickname, _dice_buffer_text(nickname, user_id, roll), message_type="dice")
            return reply
        if command in {".ra", ".检定"}:
            parsed = parse_check_command_args(command, args)
            rule = get_rule_system(settings.rule_system)
            card = card_store.load_card(settings.campaign_id, user_id)
            result = rule.check(parsed.name, card, args=parsed.rest)
            reply = rule.render_check_result(result)
            if not result.detail.get("missing_skill"):
                turn_manager.buffer_message(group_id, user_id, nickname, _check_buffer_text(nickname, user_id, result), message_type="check")
            return reply
        if command == ".角色卡模板":
            system = RuleSystemName.from_command(args.strip()) if args.strip() else settings.rule_system
            return get_template(system)
        if command == ".生成角色卡":
            return await generate_character_card(group_id, user_id, args)
        if command == ".导入角色卡":
            ok, msg = card_store.import_yaml(settings.campaign_id, user_id, args)
            return msg if ok else "导入失败：" + msg
        if command in {".我的角色卡", ".查看角色卡"}:
            target = (extract_mentioned_user_ids(args) or [user_id])[0]
            return card_store.render_card_summary(settings.campaign_id, target)
        if command == ".添加玩家":
            users = extract_mentioned_user_ids(args)
            if not users:
                raise ValueError("请使用 .添加玩家 @QQ号。示例：.添加玩家 @123456")
            for uid in users:
                turn_manager.add_player(group_id, uid)
            return "已添加玩家：" + "、".join(users)
        if command == ".移除玩家":
            users = extract_mentioned_user_ids(args)
            if not users:
                raise ValueError("请使用 .移除玩家 @QQ号。示例：.移除玩家 @123456")
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
                    raise ValueError("请使用 .等待 @玩家1 @玩家2，或 .等待 全员。示例：.等待 @123456")
            settings = turn_manager.set_required(group_id, set(users))
            return "当前等待：" + ("、".join(sorted(settings.required_players or settings.active_players)) or "无")
        if command == ".跳过":
            users = set(extract_mentioned_user_ids(args))
            if not users:
                raise ValueError("请使用 .跳过 @玩家。示例：.跳过 @123456")
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
        return "未知指令。发送 .帮助 查看可用指令。"
    except ValueError as exc:
        return f"参数错误：{exc}"


async def generate_character_card(group_id: str, user_id: str, description: str) -> str:
    settings = turn_manager.get_settings(group_id)
    template = get_template(settings.rule_system)
    desc = description.strip()
    if not desc:
        return "请给一句角色描述。示例：.生成角色卡 胆小的图书管理员"
    yaml_text = await turn_manager.ai.generate_character_card_yaml(settings.rule_system.value, desc, template)
    if yaml_text:
        ok, msg = card_store.import_yaml(settings.campaign_id, user_id, yaml_text)
        if ok:
            return msg + "\n已根据你的描述生成并导入角色卡。"
        return "AI 生成了角色卡，但校验未通过：" + msg + "\n你可以用 .角色卡模板 手动填写后发送 .导入角色卡 <YAML文本>。"
    return "\n".join([
        "当前没有配置 AI API，先给你一份可填写模板：",
        template,
        "填写时可以先回答这几个问题：你的职业是什么？三个最擅长的技能是什么？有什么明显弱点或重要随身物品？",
        "填好后发送：.导入角色卡 <YAML文本>",
    ])


def help_text(topic: str = "") -> str:
    key = topic.strip()
    pages = {
        "骰点": "骰点示例：\n.r 1d100\n.r 2d6+1\n.rd 1d20+3\n骰点结果会写入当前回合，方便 KP 结算时引用。",
        "检定": "检定示例：\n.ra 侦查\n.ra 观察\n.检定 力量 DC15\nCOC 无角色卡时会使用默认值；DND 请带 DC，例如 .检定 察觉 DC12。",
        "角色卡": "角色卡示例：\n.角色卡模板\n.生成角色卡 胆小的图书管理员\n.导入角色卡 <YAML文本>\n.我的角色卡",
        "管理": "管理示例：\n.添加玩家 @123456\n.等待 全员\n.本轮结束\n.暂停\n.继续\n这些通常需要 KP / 群管理员权限。",
    }
    if key in pages:
        return pages[key]
    return "\n".join([
        "新手玩法：直接描述行动，例如“我想翻找书架找线索”。KP 结算时会告诉你要不要检定，并给出可复制指令。",
        "常用指令：",
        ".r 1d100",
        ".ra 侦查",
        ".检定 力量 DC15",
        ".角色卡模板",
        ".生成角色卡 胆小的图书管理员",
        "分主题帮助：.帮助 骰点 / .帮助 检定 / .帮助 角色卡 / .帮助 管理",
    ])


def _dice_buffer_text(nickname: str, user_id: str, roll: DiceRoll) -> str:
    return f"{nickname}({user_id}) 已骰点：表达式={roll.expression}，原始点数={roll.dice}，修正值={roll.modifier:+d}，最终结果={roll.total}"


def _check_buffer_text(nickname: str, user_id: str, result: CheckResult) -> str:
    target = f"技能值={result.target}" if result.target is not None else "技能值=未找到"
    dc = f"，DC={result.dc}" if result.dc is not None else ""
    default = "，使用默认值" if result.detail.get("used_default") else ""
    return f"{nickname}({user_id}) 已进行{result.name}检定：{target}{dc}{default}，骰点={result.roll.total}，结果={result.success_level}"


def _write_debug_event(group_id: str, user_id: str, event_dump: dict[str, Any]) -> str:
    log_dir = get_settings().data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "qq_event_debug.jsonl"
    record = {"timestamp": now_iso(), "group_id": group_id, "user_id": user_id, "event": event_dump}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return f"已写入事件调试日志：{path}"

