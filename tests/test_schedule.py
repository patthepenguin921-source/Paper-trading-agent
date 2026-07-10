from datetime import datetime
from zoneinfo import ZoneInfo

from schedule import market_phase

ET = ZoneInfo("America/New_York")


def _et(hour, minute):
    # A fixed EDT date so no test depends on the DST transition.
    return datetime(2026, 7, 10, hour, minute, tzinfo=ET).astimezone(ZoneInfo("UTC"))


def test_quiet_overnight():
    assert market_phase(_et(2, 0)) == "quiet"
    assert market_phase(_et(23, 59)) == "quiet"


def test_pre_market_review_window():
    assert market_phase(_et(8, 30)) == "pre_market_review"
    assert market_phase(_et(8, 44)) == "pre_market_review"


def test_pre_market_review_window_is_exclusive_at_845():
    assert market_phase(_et(8, 45)) == "quiet"


def test_quiet_between_review_and_active():
    assert market_phase(_et(9, 0)) == "quiet"


def test_active_window():
    assert market_phase(_et(9, 15)) == "active_window"
    assert market_phase(_et(12, 0)) == "active_window"
    assert market_phase(_et(16, 59)) == "active_window"


def test_active_window_ends_at_5pm():
    assert market_phase(_et(17, 0)) == "quiet"


def test_defaults_to_now_when_no_arg():
    # Just confirm it doesn't blow up and returns a valid phase.
    assert market_phase() in ("pre_market_review", "active_window", "quiet")
