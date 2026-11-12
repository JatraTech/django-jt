import calendar
from datetime import date

from django.utils.dateparse import parse_duration
from django.utils.timezone import datetime, timedelta

__version__ = "0.3.1"


def str_to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return False
    return value.strip().lower() in {"true", "1", "yes"}


def get_last_date_of_week(year: int, week: int) -> datetime:
    """
    Returns the last date (Sunday) of a given ISO week and year.

    """
    first_week_start = datetime.fromisocalendar(year, week, 1)
    last_date = first_week_start + timedelta(days=6)
    return last_date


def get_first_date_of_current_month() -> date:
    """
    Returns the first date of the current month.

    """
    today = datetime.today()
    return datetime(today.year, month=today.month, day=1).date()


def get_last_date_of_current_month() -> date:
    """
    Returns the last date of the current month.

    """
    today = datetime.today()
    return datetime(
        today.year,
        month=today.month,
        day=calendar.monthrange(today.year, today.month)[1],
    ).date()


def format_duration_hhmmss(value):
    if value in (None, ""):
        return value

    duration = value if isinstance(value, timedelta) else parse_duration(str(value))
    if duration is None:
        return value

    total_seconds = int(duration.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02}:{minutes:02}:{seconds:02}"


def format_duration_hhmmday(value):
    if value in (None, ""):
        return value

    duration = value if isinstance(value, timedelta) else parse_duration(str(value))
    if duration is None:
        return value

    total_seconds = int(duration.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{days} {hours:02}:{minutes:02}:{seconds:02}"
