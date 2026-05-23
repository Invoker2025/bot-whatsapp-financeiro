from datetime import datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import APP_TIMEZONE


@lru_cache(maxsize=1)
def app_timezone():
    try:
        return ZoneInfo(APP_TIMEZONE)
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=-3), "UTC-03:00")


def now_local() -> datetime:
    return datetime.now(app_timezone()).replace(tzinfo=None)
