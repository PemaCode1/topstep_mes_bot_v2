from datetime import datetime, time
from zoneinfo import ZoneInfo


def parse_hhmm(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def to_session_time(dt: datetime, timezone_name: str) -> time:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
    return dt.astimezone(ZoneInfo(timezone_name)).time().replace(tzinfo=None)


def is_time_between(current: time, start: str, end: str) -> bool:
    return parse_hhmm(start) <= current <= parse_hhmm(end)
