from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trpg_bot.config import get_settings
from trpg_bot.core_handler import handle_text, store
from trpg_bot.permissions import UserContext


HELP = """本地 QQ 群模拟器（无需 QQ、无需 API）
/as <user_id> <昵称>  切换当前发言者
/su                   把当前用户加入运行期 superuser
/admin on|off         设置当前用户是否为群管理员
/group <id>           切换群号
/quit                 退出
其他输入都会当作群消息处理，例如：.帮助、.ra 侦查、我想翻找书架找线索
"""


async def main() -> None:
    settings = get_settings()
    settings.ensure_dirs()
    store.init_db()
    group_id = "sim"
    user_id = "1"
    nickname = "测试者"
    is_admin = False
    print(HELP)
    while True:
        try:
            line = input(f"[群 {group_id}][{nickname}({user_id}){' 管理员' if is_admin else ''}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line == "/quit":
            break
        if line.startswith("/as "):
            parts = line.split(maxsplit=2)
            if len(parts) < 3:
                print("用法：/as <user_id> <昵称>")
                continue
            user_id, nickname = parts[1], parts[2]
            print(f"已切换到 {nickname}({user_id})")
            continue
        if line == "/su":
            settings.superusers.add(user_id)
            print(f"{user_id} 已加入本次运行的 superuser")
            continue
        if line.startswith("/admin "):
            value = line.split(maxsplit=1)[1]
            is_admin = value == "on"
            print(f"管理员身份：{'on' if is_admin else 'off'}")
            continue
        if line.startswith("/group "):
            group_id = line.split(maxsplit=1)[1].strip() or group_id
            print(f"已切换群号：{group_id}")
            continue
        user = UserContext(user_id=user_id, group_id=group_id, is_group_admin=is_admin)
        replies = await handle_text(group_id, user, nickname, line)
        for reply in replies:
            print(reply)


if __name__ == "__main__":
    asyncio.run(main())
