import calendar
from datetime import date

from django.utils.timezone import datetime, timedelta

__version__ = "0.1.0"


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
