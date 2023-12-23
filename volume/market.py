import datetime

from django.utils import timezone


MARKET_OPEN = datetime.time(9, 30)
MARKET_CLOSE = datetime.time(16, 0)
MARKET_LAST_MINUTE = datetime.time(15, 59)
# MARKET_CLOSE = datetime.time(9, 59)

ONE_MINUTE = datetime.timedelta(minutes=1)
ONE_DAY = datetime.timedelta(days=1)


def open_close(day=None):
    if day is None:
        day = timezone.localdate()

    open_dt = timezone.make_aware(datetime.datetime.combine(day, MARKET_OPEN))
    close_dt = timezone.make_aware(datetime.datetime.combine(day, MARKET_CLOSE))

    return open_dt, close_dt


def first_last_minute(day=None):
    if day is None:
        day = timezone.localdate()

    first_dt = timezone.make_aware(datetime.datetime.combine(day, MARKET_OPEN))
    last_dt = timezone.make_aware(datetime.datetime.combine(day, MARKET_LAST_MINUTE))

    return first_dt, last_dt


def current_minute():
    now = timezone.now()
    return now.replace(second=0, microsecond=0) - ONE_MINUTE


def is_closing_minute(dt):
    return dt == timezone.make_aware(datetime.datetime.combine(dt.date(), MARKET_CLOSE) - ONE_MINUTE)


def is_opening_minute(dt):
    return dt.time() == MARKET_OPEN


def count_minutes_in_trading_day():
    today_open, today_close = open_close()
    return int((today_close - today_open).total_seconds() // 60)


def trading_minutes(until=None):
    if isinstance(until, datetime.date):
        until = datetime.datetime.combine(until, MARKET_CLOSE)

    if until is None:
        until = timezone.now()

    if timezone.is_naive(until):
        until = timezone.make_aware(until)

    until = min(until, timezone.now() - ONE_MINUTE)

    current, _ = open_close(until.date())

    while current < until:
        yield current
        current += ONE_MINUTE


def all_trading_minutes(day=None):
    current, close = open_close(day)

    while current < close:
        yield current
        current += ONE_MINUTE


def is_weekday(day):
    return day.weekday() < 5


def _day_next(day, delta):
    delta_dt = delta*datetime.timedelta(days=1)
    while True:
        day += delta_dt
        if is_weekday(day):
            return day


def previous_trading_day(day):
    return _day_next(day, -1)


def next_trading_day(day):
    return _day_next(day, 1)
