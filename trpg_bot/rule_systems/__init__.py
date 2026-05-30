from trpg_bot.models import RuleSystemName
from trpg_bot.rule_systems.base import BaseRuleSystem
from trpg_bot.rule_systems.coc7 import COC7RuleSystem
from trpg_bot.rule_systems.custom import CustomRuleSystem
from trpg_bot.rule_systems.dnd5e import DND5ERuleSystem


def get_rule_system(name: RuleSystemName | str) -> BaseRuleSystem:
    value = RuleSystemName.from_command(str(name)) if not isinstance(name, RuleSystemName) else name
    return {
        RuleSystemName.COC7: COC7RuleSystem(),
        RuleSystemName.DND5E: DND5ERuleSystem(),
        RuleSystemName.CUSTOM: CustomRuleSystem(),
    }[value]

__all__ = ["BaseRuleSystem", "COC7RuleSystem", "DND5ERuleSystem", "CustomRuleSystem", "get_rule_system"]
