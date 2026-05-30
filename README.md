# QQ AI 跑团机器人（MVP）

这是一个本地优先运行的 QQ 群 AI KP / DM 机器人 MVP。它不是“每条消息都回复”的聊天机器人，而是先把多人发言写入回合缓冲区，再根据自动 / 手动 / 混合模式统一结算。

## 已实现项目结构

```text
trpg_qq_bot/
  pyproject.toml
  README.md
  .env.example
  bot.py
  trpg_bot/
    config.py              # .env 配置读取
    permissions.py         # 集中权限判断
    commands.py            # 中文指令解析
    qq_events.py           # NoneBot2 / QQ 事件接入
    turn_manager.py        # 回合缓冲、回复模式、结算锁
    dice.py                # 骰点表达式解析
    character_cards.py     # YAML 角色卡模板 / 导入 / 查看
    rule_systems/          # COC7 / DND5E / CUSTOM 抽象
    memory/                # SQLite、Markdown、关键词检索
    ai/                    # OpenAI-compatible client、Prompt、JSON 解析
    models.py
    utils.py
  data/
    campaigns/
    logs/
    characters/
  tests/
```

## 本地运行

> 默认按本地 WebSocket 思路配置。Webhook 需要公网地址，不适合作为默认本地方案。

1. 安装 Python 3.11+
2. 安装依赖：

```bash
python -m pip install -e '.[dev]'
```

3. 复制配置：

```bash
cp .env.example .env
```

4. 编辑 `.env`：

- `QQ_BOTS`：填写 QQ 官方 Bot 的 app id / token / secret。
- `TRPG_SUPERUSERS`：填写机器人超级用户 QQ 号，逗号分隔。
- `TRPG_AI_API_KEY`：可留空；留空时会返回本地占位 KP 回复，便于先测试回合流程。
- `TRPG_AI_BASE_URL` / `TRPG_AI_MODEL`：支持 OpenAI-compatible API。

5. 启动：

```bash
python bot.py
```

首次启动会初始化 `data/trpg.sqlite3`，并创建 `data/campaigns`、`data/characters` 等目录。

## 核心行为

- 普通玩家消息只进入当前回合缓冲区，不会逐条调用 AI。
- 骰点和检定即时回复，不进入回合缓冲区。
- `.本轮结束` / `.强制回复` 只有 KP / 群管理员 / superuser 可以触发。
- 同一群的结算使用 per-group lock，避免连续强制回复重复结算同一回合。
- 支持 `.暂停` / `.继续`：暂停后普通群消息不进入回合缓冲区，但骰点和管理指令仍可用。
- AI 回复成功写入 Markdown 和 SQLite 后，才进入下一回合。
- AI 输出必须是 JSON；解析失败时不会崩溃，会保留原始回复并提示 KP。

## 指令

### 管理指令（KP / 群管理员 / superuser）

- `.模式 自动`
- `.模式 手动`
- `.模式 混合`
- `.规则 COC`
- `.规则 DND`
- `.规则 自定义`
- `.添加玩家 @123456`
- `.移除玩家 @123456`
- `.等待 @123456 @234567`
- `.等待 全员`
- `.跳过 @123456`
- `.本轮结束`
- `.强制回复`
- `.清空本轮`
- `.暂停`
- `.继续`
- `.导入角色卡 <YAML文本>`

### Superuser 调试指令

- `.调试事件`：把当前 `event.model_dump()` 追加写入 `data/logs/qq_event_debug.jsonl`，用于确认真实 QQ 官方 Bot 事件中的群号、用户、管理员、@、notice / 拍一拍字段。

### 玩家指令

- `.r 1d100`
- `.r 1d20+3`
- `.ra 侦查`
- `.rd 1d20+3`
- `.检定 侦查`
- `.检定 力量 DC15`
- `.角色卡模板`
- `.角色卡模板 COC`
- `.角色卡模板 DND`
- `.查看角色卡 @123456`
- `.我的角色卡`
- `.当前状态`（会显示运行中 / 已暂停）
- `.当前等待`
- `.当前发言`
- `.玩家列表`
- `.当前规则`

> 当前适配器如果无法解析真实 @ 消息，可以临时使用 `@123456` 这样的纯文本形式。

## 规则系统

规则系统统一实现 `BaseRuleSystem`：

- `parse_roll_command()`
- `roll()`
- `check()`
- `render_check_result()`
- `get_character_template()`
- `validate_character_card()`

### COC7

支持 `d100` 检定、技能值读取角色卡、`.ra 侦查`、`.检定 侦查`。大失败规则第一版采用常见版本：技能值 `< 50` 时 `96-100` 大失败，技能值 `>= 50` 时 `100` 大失败；代码中保留了未来配置化入口。

### DND5E / CUSTOM

DND5E 第一版支持 d20 + 属性修正 / DC 判定；熟练加值接口后续扩展。CUSTOM 第一版提供通用骰点和模板。

## 角色卡

使用 YAML 纯文本导入，保存到：

```text
data/characters/{campaign_id}/{user_id}.yaml
```

同时会同步基础索引到 SQLite 的 `character_cards` 表。

## 长期记忆

### SQLite

初始化表：

- `campaigns`
- `players`
- `campaign_players`
- `turns`
- `turn_messages`
- `memories`
- `settings`
- `character_cards`

### Markdown

AI 回复后追加写入：

```text
data/campaigns/{campaign_id}/
  session_logs/
  characters/
  npcs.md
  locations.md
  clues.md
  world_state.md
  unresolved_threads.md
  timeline.md
```

Markdown 只追加，不覆盖。

## 真实 QQ 接入时如何调试 event 字段

QQ 官方 Bot 适配器在不同事件类型、权限和版本下，字段名称可能不同。例如群号可能来自 `group_id`、频道场景可能来自 `guild_id` / `channel_id`，管理员信息、@ 解析、notice / 拍一拍字段也可能不同。

建议首次接入真实 QQ 环境时：

1. 在 `.env` 中把你的 QQ 号加入 `TRPG_SUPERUSERS`。
2. 在目标群里发送 `.调试事件`。
3. 查看 `data/logs/qq_event_debug.jsonl`，确认当前适配器实际提供的 `event.model_dump()` 字段；该指令即使暂时无法解析 `group_id`，也会以 `unknown` 记录，便于排查字段名。
4. 如需适配特殊事件（例如拍一拍），优先根据日志扩展 `trpg_bot/qq_events.py` 中的 `_get_group_id()`、`_get_user_id()`、`_is_admin()` 或 `handle_poke_event()`，不要假设所有 QQ 事件都有同一套字段。

该调试指令是 superuser-only，不会开放给普通 KP 或群管理员。

## 拍一拍说明

保留了 `handle_poke_event()` 接口，但第一版不把事件结构写死。QQ 官方适配器对拍一拍 / notice 字段的支持可能随版本和场景变化。稳定替代方案是 `.强制回复`，并且同样需要 KP / 群管理员权限。

## 测试

```bash
pytest
```
