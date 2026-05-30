from __future__ import annotations

from pathlib import Path
from typing import Any

from trpg_bot import simple_yaml as yaml

from trpg_bot.config import get_settings
from trpg_bot.memory.sqlite_store import SQLiteStore
from trpg_bot.models import RuleSystemName
from trpg_bot.rule_systems import get_rule_system


def get_template(system: RuleSystemName | str = RuleSystemName.COC7) -> str:
    return get_rule_system(system).get_character_template()


class CharacterCardStore:
    def __init__(self, sqlite: SQLiteStore | None = None) -> None:
        self.settings = get_settings()
        self.sqlite = sqlite or SQLiteStore()

    def card_path(self, campaign_id: str, user_id: str) -> Path:
        return self.settings.data_dir / "characters" / campaign_id / f"{user_id}.yaml"

    def import_yaml(self, campaign_id: str, user_id: str, yaml_text: str) -> tuple[bool, str]:
        try:
            card = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            return False, f"YAML 解析失败：{exc}"
        if not isinstance(card, dict):
            return False, "角色卡必须是 YAML 映射。"
        try:
            system_name = RuleSystemName.from_command(str(card.get("system", "COC7")))
        except ValueError as exc:
            return False, str(exc)
        rule = get_rule_system(system_name)
        ok, errors = rule.validate_character_card(card)
        if not ok:
            return False, "角色卡校验失败：" + "；".join(errors)
        path = self.card_path(campaign_id, user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(card, allow_unicode=True, sort_keys=False), encoding="utf-8")
        self.sqlite.upsert_character_card(campaign_id, user_id, system_name.value, str(card.get("character_name") or ""), str(path))
        return True, f"已导入角色卡：{card.get('character_name') or '未命名角色'}"

    def load_card(self, campaign_id: str, user_id: str) -> dict[str, Any] | None:
        path = self.card_path(campaign_id, user_id)
        if not path.exists():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None

    def render_card_summary(self, campaign_id: str, user_id: str) -> str:
        card = self.load_card(campaign_id, user_id)
        if not card:
            return "未找到该玩家的角色卡。"
        skills = card.get("skills") if isinstance(card.get("skills"), dict) else {}
        top_skills = "、".join(f"{k}:{v}" for k, v in list(skills.items())[:10])
        return "\n".join([f"角色：{card.get('character_name') or '未命名'}", f"系统：{card.get('system')}", f"玩家：{card.get('player') or user_id}", f"技能：{top_skills or '无'}"])
