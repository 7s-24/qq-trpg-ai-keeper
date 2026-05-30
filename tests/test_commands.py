import pytest

from trpg_bot.commands import parse_check_command_args


def test_parse_ra_check_args():
    parsed = parse_check_command_args(".ra", "侦查")
    assert parsed.name == "侦查"
    assert parsed.rest == "侦查"
    assert parsed.dc is None


def test_parse_dnd_check_args_with_dc():
    parsed = parse_check_command_args(".检定", "力量 DC15")
    assert parsed.name == "力量"
    assert parsed.rest == "DC15"
    assert parsed.dc == 15


def test_parse_check_args_requires_name():
    with pytest.raises(ValueError, match="请指定检定名称"):
        parse_check_command_args(".检定", "")
