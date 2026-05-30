from trpg_bot.rule_systems.coc7 import COC7RuleSystem, coc7_success_level


def test_coc7_success_levels():
    assert coc7_success_level(1, 60) == ("大成功", True)
    assert coc7_success_level(10, 60) == ("极难成功", True)
    assert coc7_success_level(30, 60) == ("困难成功", True)
    assert coc7_success_level(60, 60) == ("普通成功", True)
    assert coc7_success_level(80, 60) == ("失败", False)
    assert coc7_success_level(100, 60) == ("大失败", False)
    assert coc7_success_level(96, 40) == ("大失败", False)


def test_coc7_template_validates():
    rule = COC7RuleSystem()
    from trpg_bot import simple_yaml as yaml

    card = yaml.safe_load(rule.get_character_template())
    ok, errors = rule.validate_character_card(card)
    assert ok, errors
