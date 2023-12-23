import csv
import datetime

from django.db import transaction
from django.utils import timezone

from .models import Symbol, DataDay, Minute


def process_csv(path):
    minutes, days = load_from_csv(path)
    save_data(minutes, days)
    return len(minutes), len(days)


@transaction.atomic
def save_data(minutes, days):
    for symbol_str, date in days:
        try:
            symbol = Symbol.objects.get(symbol=symbol_str)
        except Symbol.DoesNotExist:
            symbol = Symbol.objects.get(name=symbol_str)

        dd, created = DataDay.objects.get_or_create(
            symbol=symbol,
            day=date,
            defaults={"state": DataDay.State.COMPLETE},
        )
        if not created:
            dd.state = DataDay.State.COMPLETE
            dd.save()

    Minute.objects.bulk_create(minutes)


def load_from_csv(path):
    minutes = []
    days = set()
    symbols = {}

    with path.open() as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            minute_obj = parse_csv_row(row, symbols)
            minutes.append(minute_obj)
            days.add((minute_obj.symbol, minute_obj.time.date()))

    return minutes, days


def parse_csv_row(row, symbols):
    symbol_str, date_str, time_str, last_str, volume_str, cumulative_volume_str, slope_str = row
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    time = datetime.datetime.strptime(time_str, "%H:%M:%S").time()
    dt = datetime.datetime.combine(date, time)
    dt = timezone.make_aware(dt, timezone.utc)

    try:
        volume = float(volume_str)
    except ValueError:
        volume = None
    try:
        cumulative_volume = float(cumulative_volume_str)
    except ValueError:
        cumulative_volume = None
    try:
        last = float(last_str)
    except ValueError:
        last = None
    try:
        slope = float(slope_str)
    except ValueError:
        slope = None

    if symbol_str in symbols:
        symbol = symbols[symbol_str]
    else:
        try:
            symbol = Symbol.objects.get(symbol=symbol_str)
        except Symbol.DoesNotExist:
            symbol = Symbol.objects.get(name=symbol_str)
        symbols[symbol_str] = symbol

    return Minute(
        time=dt,
        symbol=symbol,
        last=last,
        volume=volume,
        cumulative_volume=cumulative_volume,
        slope=slope,
    )
