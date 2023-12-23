from .models import Minute, DataDay, Correlation, Symbol, RollingCorrelation

from . import calculate
from . import logic
from . import market


def update_day_with_slope(data_day):
    data = logic.data_day(data_day.symbol, data_day.day)
    if (data_day.state != DataDay.State.COMPLETE or
            not data or data[0].slope is not None):
        # print("Not valid")
        return

    previous_value = None
    slope = None
    for d in data:
        value = d.volume
        raise NotImplemented("Changed how calculate_slope works - fix this")
        slope = calculate.calculate_slope(value, previous_value, slope)
        previous_value = value
        d.slope = slope
        # print(f"{d.time:%H:%M:%S}\t{value}\t{slope}")

    Minute.objects.bulk_update(data, ["slope"])


def update_slopes(after=None):
    days = DataDay.objects.filter(state=DataDay.State.COMPLETE)
    if after is not None:
        days = days.filter(day__gt=after)

    print(f"There are {len(days)} days")

    for i, day in enumerate(days):
        if i and i % 100 == 0:
            print(f"{i} / {len(days)} ({100*i/len(days):.0f})")

        update_day_with_slope(day)


def backfill_all_symbols_for_day(day):
    count = 0
    symbols = Symbol.objects.filter(active=True)
    for symbol in symbols:
        try:
            dd = DataDay.objects.get(symbol=symbol, day=day)
            if dd.state == DataDay.State.LIVE:
                print(f"Set {symbol.symbol} to pending")
                dd.state = DataDay.State.PENDING
                dd.save()
                count += 1
        except DataDay.DoesNotExist:
            print(f"Create {symbol.symbol}")
            dd = DataDay(symbol=symbol, day=day, state=DataDay.State.PENDING)
            dd.save()
            count += 1

    return count


def load_all_day_data(symbol, day):
    symbol_obj = Symbol.objects.get(symbol=symbol)
    market_open, market_close = market.open_close(day)

    data_days = DataDay.objects.filter(symbol=symbol_obj, day=day)
    correlations = Correlation.objects.filter(symbol=symbol_obj, day=day)
    minutes = Minute.timescale.filter(symbol=symbol_obj,
                                      time__gte=market_open,
                                      time__lte=market_close)

    return minutes, data_days, correlations


def add_correlations(after=None):
    days = DataDay.objects.filter(state=DataDay.State.COMPLETE)
    if after is not None:
        days = days.filter(day__gt=after)

    print(f"There are {len(days)} days")

    for i, day in enumerate(days):
        print(i, day)
        if Correlation.objects.filter(symbol=day.symbol, day=day.day).count() == len(Correlation.DataType):
            continue

        data = logic.data_day(day.symbol, day.day)

        if not Correlation.objects.filter(symbol=day.symbol,
                                          day=day.day,
                                          data_type=Correlation.DataType.VOLUME).exists():
            try:
                corr = calculate.volume_correlation(data)
                c = Correlation(
                    symbol=day.symbol,
                    day=day.day,
                    data_type=Correlation.DataType.VOLUME,
                    value=corr)
                c.save()
            except (ValueError, TypeError):
                pass


        if not Correlation.objects.filter(symbol=day.symbol,
                                          day=day.day,
                                          data_type=Correlation.DataType.SLOPE).exists():
            try:
                corr = calculate.slope_correlation(data)
                c = Correlation(
                    symbol=day.symbol,
                    day=day.day,
                    data_type=Correlation.DataType.SLOPE,
                    value=corr)
                c.save()
            except (ValueError, TypeError):
                pass


def add_rolling_correlations(after=None):
    days = DataDay.objects.filter(state=DataDay.State.COMPLETE)
    if after is not None:
        days = days.filter(day__gt=after)

    print(f"There are {len(days)} days")

    for i, day in enumerate(days):
        print(i, day)

        rolls = logic.rolling_correlations_for_day(day.symbol, day.day)
        RollingCorrelation.objects.bulk_create(rolls)

        print(f"Saved {len(rolls)} minutes")
