from datetime import timedelta

from django_jt import format_duration_hhmmday, format_duration_hhmmss


def test_format_duration_hhmmss_timedelta():
    assert format_duration_hhmmss(timedelta(hours=1, minutes=2, seconds=3)) == "01:02:03"


def test_format_duration_hhmmss_iso_string():
    assert format_duration_hhmmss("PT1H2M3S") == "01:02:03"


def test_format_duration_hhmmss_none_passthrough():
    assert format_duration_hhmmss(None) is None


def test_format_duration_hhmmday_with_days():
    assert format_duration_hhmmday(timedelta(days=1, hours=2, minutes=3, seconds=4)) == "1 02:03:04"
