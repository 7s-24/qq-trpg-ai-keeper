from trpg_bot.models import CampaignSettings
from trpg_bot.permissions import UserContext, can_execute, is_kp


def test_superuser_is_kp(monkeypatch):
    from trpg_bot.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "superusers", {"1"})
    assert is_kp(UserContext("1", "g"), CampaignSettings("c", "g"))


def test_player_cannot_force_reply():
    assert not can_execute(".强制回复", UserContext("2", "g"), CampaignSettings("c", "g"))


def test_player_can_roll():
    assert can_execute(".r", UserContext("2", "g"), CampaignSettings("c", "g"))
