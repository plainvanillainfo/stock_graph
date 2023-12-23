import csv
import datetime
import io
import operator
from collections import OrderedDict, defaultdict

import django.db
from django.db.models import Q
from django.utils import timezone

from . import api
from . import calculate
from . import market
from .models import Symbol, DataDay, Minute, Chart, IncomingPrice, Correlation, Group, RollingCorrelation, MarketHoliday, SystemSetting


DATA_HEADER = ["Symbol", "Date", "Minute UTC", "Last Trade", "Minute Volume", "Daily Volume", "Slope"]

ROLLING_CORRELATION_WINDOW = 15
ROLLING_CORRELATION_INTERVAL = datetime.timedelta(minutes=ROLLING_CORRELATION_WINDOW)


class InvalidSymbol(Exception):
    pass


class SymbolAlreadyExists(Exception):
    pass


def add_group(name, group_type):
    return Group.objects.create(name=name, group_type=group_type)


def add_chart(name):
    return Chart.objects.create(name=name)


def delete_chart(slug):
    chart = Chart.objects.get(slug=slug)
    chart.delete()


def delete_group(slug):
    group = Group.objects.get(slug=slug)
    group.delete()


def rename_chart(slug, name):
    chart = Chart.objects.get(slug=slug)
    chart.name = name
    chart.save()


def rename_group(slug, name):
    group = Group.objects.get(slug=slug)
    group.name = name
    group.save()


def change_chart_type(slug, data_type):
    types = {
        "Volume": Chart.DataType.VOLUME,
        "Slope": Chart.DataType.SLOPE,
    }
    chart = Chart.objects.get(slug=slug)
    chart.data_type = types[data_type]
    chart.save()


@django.db.transaction.atomic
def update_chart(slug, symbols):
    chart = Chart.objects.get(slug=slug)
    symbol_objs = Symbol.objects.filter(symbol__in=symbols)
    chart.symbols.set(symbol_objs)


@django.db.transaction.atomic
def update_group(slug, symbols):
    group = Group.objects.get(slug=slug)
    symbol_objs = Symbol.objects.filter(symbol__in=symbols)
    group.symbols.set(symbol_objs)


def symbol_exists(symbol):
    return Symbol.objects.filter(symbol=symbol).exists()


def add_symbol(symbol):
    api_data = api.verify_symbol(symbol)
    if api_data is None:
        raise InvalidSymbol

    try:
        return Symbol.objects.create(symbol=symbol)
    except django.db.IntegrityError:
        raise SymbolAlreadyExists


def activate_symbol(symbol):
    symbol_obj = Symbol.objects.get(symbol=symbol)
    symbol_obj.active = True
    symbol_obj.save()


def deactivate_symbol(symbol):
    symbol_obj = Symbol.objects.get(symbol=symbol)
    symbol_obj.active = False
    symbol_obj.save()


def set_symbol_colour(symbol, colour):
    symbol_obj = Symbol.objects.get(symbol=symbol)
    symbol_obj.colour = colour
    symbol_obj.save()


def queue_past_days(symbol, number):
    start = datetime.date.today() - datetime.timedelta(days=number)
    return queue_days_since(symbol, start)


def queue_days_since(symbol, date):
    symbol_obj = Symbol.objects.get(symbol=symbol)
    today = datetime.date.today()

    existing = set(DataDay.objects.filter(symbol=symbol_obj, day__gte=date).values_list("day", flat=True))
    day_objects = []

    while date < today:
        if date not in existing and date.weekday() < 5:
            obj = DataDay(symbol=symbol_obj, day=date)
            day_objects.append(obj)

        date += datetime.timedelta(days=1)

    DataDay.objects.bulk_create(day_objects)

    return len(day_objects)


def queue_active_symbols():
    symbols = Symbol.objects.filter(active=True)
    today = timezone.localdate()
    day_objects = []
    today_close = timezone.make_aware(datetime.datetime.combine(timezone.localdate(), market.MARKET_CLOSE))

    if timezone.now() <= today_close:
        comp = operator.lt
    else:
        comp = operator.le

    for symbol in symbols:
        dd = DataDay.objects.filter(symbol=symbol).last()
        if not dd:
            continue

        day = dd.day
        day += datetime.timedelta(days=1)

        while comp(day, today):
            if market.is_weekday(day):
                obj = DataDay(symbol=symbol, day=day)
                day_objects.append(obj)

            day += datetime.timedelta(days=1)

    DataDay.objects.bulk_create(day_objects)

    return len(day_objects)


def days_to_range(start, end):
    start_dt = datetime.datetime.combine(start, datetime.time(0, 0))
    end_dt = datetime.datetime.combine(end + datetime.timedelta(days=1), datetime.time(0, 0))
    return [timezone.make_aware(start_dt), timezone.make_aware(end_dt)]


def day_to_range(day):
    start = datetime.datetime.combine(day, datetime.time(0, 0))
    end = datetime.datetime.combine(day + datetime.timedelta(days=1), datetime.time(0, 0))
    return [timezone.make_aware(start), timezone.make_aware(end)]


def data_range(symbol, range_):
    return Minute.timescale.filter(symbol__symbol=symbol, time__range=range_)


def data_day(symbol, day):
    return Minute.timescale.filter(symbol__symbol=symbol, time__range=day_to_range(day))


def rolling_correlation_data_day(symbol, day, data_type):
    return RollingCorrelation.timescale.filter(symbol__symbol=symbol, time__range=day_to_range(day), window=ROLLING_CORRELATION_WINDOW, data_type=data_type)


def data_all(symbol):
    return Minute.timescale.filter(symbol__symbol=symbol)


def data_multiple(symbol, days):
    query = Q()
    for day in days:
        query |= Q(time__range=day_to_range(day))

    return Minute.timescale.filter(query, symbol__symbol=symbol)


def name_for_symbol(symbol):
    sym = Symbol.objects.get(symbol=symbol)
    return sym.display_name


def minute_before(symbol, minute):
    return Minute.timescale.get(symbol__symbol=symbol, time=(minute - datetime.timedelta(minutes=1)))


def incoming_price_for(symbol, minute):
    qs = IncomingPrice.objects.filter(symbol=symbol, time=(minute - datetime.timedelta(minutes=1)))
    if not qs:
        return None
    else:
        return qs[0]


def clear_incoming_prices():
    IncomingPrice.objects.all().delete()


def weights(symbol_obj):
    return {weight.symbol: weight.weight
            for weight in symbol_obj.weights.all()}


def data_csv(qs):
    data = io.StringIO()
    writer = csv.writer(data)
    writer.writerow(DATA_HEADER)
    writer.writerows((row.symbol, row.time.strftime("%F"), row.time.strftime("%T"), row.last, row.volume, row.cumulative_volume, row.slope) for row in qs)
    return data.getvalue()


class Echo:
    def write(self, value):
        return value

def stream_data_csv(qs):
    # Adapted from Django docs
    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)

    yield writer.writerow(DATA_HEADER)
    for row in qs:
        yield writer.writerow((
            row.symbol.display_name,
            row.time.strftime("%F"),
            row.time.strftime("%T"),
            row.last,
            row.volume,
            row.cumulative_volume,
            row.slope,
        ))


def correlation_dict(today_data, previous_data):
    data = OrderedDict()
    for d in today_data:
        data[d.symbol.symbol] = {"today": d.value, "display_name": d.symbol.display_name}

    for d in previous_data:
        if d.symbol.symbol in data:
            data[d.symbol.symbol]["previous"] = d.value

    return data


def correlation_days(today, previous_day, data_type, symbols):
    today_data = Correlation.objects.filter(symbol__in=symbols, day=today, data_type=data_type).order_by("value")
    previous_data = Correlation.objects.filter(symbol__in=symbols, day=previous_day, data_type=data_type)

    return correlation_dict(today_data, previous_data)


def correlation_objects(symbol, day, day_data):
    vc = Correlation(
        symbol=symbol,
        day=day,
        data_type=Correlation.DataType.VOLUME,
        value=calculate.volume_correlation(day_data))
    sc = Correlation(
        symbol=symbol,
        day=day,
        data_type=Correlation.DataType.SLOPE,
        value=calculate.slope_correlation(day_data))

    return vc, sc


def slope_table_minutes(current_minute):
    market_open, market_last = market.first_last_minute(current_minute.date())

    if current_minute < market_open:
        current_minute = market_open
    elif current_minute > market_last:
        current_minute = market_last

    previous_day = market.previous_trading_day(current_minute.date())
    diff = current_minute.date() - previous_day
    previous_minute = current_minute - diff
    _, previous_close = market.first_last_minute(previous_day)

    return current_minute, previous_minute, previous_close


def slope_table_dict(current_data, previous_minute_data, previous_close_data):
    data = OrderedDict()
    for d in current_data:
        data[d.symbol.symbol] = {"current": d.slope, "name": d.symbol.display_name}

    for d in previous_close_data:
        if d.symbol.symbol not in data:
            data[d.symbol.symbol] = {"name": d.symbol.display_name}
        data[d.symbol.symbol]["previous_close"] = d.slope

    for d in previous_minute_data:
        if d.symbol.symbol not in data:
            data[d.symbol.symbol] = {"name": d.symbol.display_name}
        data[d.symbol.symbol]["previous_minute"] = d.slope

    return data


def slope_table_data(symbols, current_minute):
    current_minute, previous_minute, previous_close = slope_table_minutes(current_minute)

    current_data = Minute.timescale.filter(symbol__in=symbols, time=current_minute).order_by("slope").select_related("symbol")
    previous_minute_data = Minute.timescale.filter(symbol__in=symbols, time=previous_minute).select_related("symbol")
    previous_close_data = Minute.timescale.filter(symbol__in=symbols, time=previous_close).select_related("symbol").order_by("slope")

    return (current_minute,
            previous_minute,
            previous_close,
            slope_table_dict(current_data, previous_minute_data, previous_close_data))


def comparison_table_data(symbols, start, end, use_previous_close):
    minutes = Minute.timescale.filter(symbol__in=symbols, symbol__active=True, time__gte=start, time__lte=end).select_related("symbol")
    volume_rolling = RollingCorrelation.timescale.filter(symbol__in=symbols, symbol__active=True, time__gte=start, time__lte=end, data_type=RollingCorrelation.DataType.VOLUME, window=ROLLING_CORRELATION_WINDOW).select_related("symbol")
    slope_rolling = RollingCorrelation.timescale.filter(symbol__in=symbols, symbol__active=True, time__gte=start, time__lte=end, data_type=RollingCorrelation.DataType.SLOPE, window=ROLLING_CORRELATION_WINDOW).select_related("symbol")

    if use_previous_close:
        previous_day = market.previous_trading_day(start.date())
        _, prev_last_minute = market.first_last_minute(previous_day)
        prev_close = Minute.timescale.filter(symbol__in=symbols, symbol__active=True, time=prev_last_minute).select_related("symbol")
        prev_close_prices = {m.symbol.symbol: m.last for m in prev_close}

    by_symbol = defaultdict(list)
    volume_rolling_by_symbol = defaultdict(list)
    slope_rolling_by_symbol = defaultdict(list)
    data = defaultdict(dict)

    for minute in minutes:
        by_symbol[minute.symbol.symbol].append(minute)

    for roll in volume_rolling:
        volume_rolling_by_symbol[roll.symbol.symbol].append(roll)

    for symbol, symbol_data in volume_rolling_by_symbol.items():
        if symbol_data:
            last = symbol_data[-1]
            data[symbol]["rolling_volume_correlation"] = last.value

    for roll in slope_rolling:
        slope_rolling_by_symbol[roll.symbol.symbol].append(roll)

    for symbol, symbol_data in slope_rolling_by_symbol.items():
        if symbol_data:
            last = symbol_data[-1]
            data[symbol]["rolling_slope_correlation"] = last.value

    for symbol, symbol_data in by_symbol.items():
        first, last = symbol_data[0], symbol_data[-1]
        data[symbol]["symbol"] = symbol
        data[symbol]["name"] = first.symbol.display_name
        data[symbol]["slope_diff"] = last.slope - first.slope

        # Calculate price difference
        if use_previous_close:
            start_price = prev_close_prices.get(symbol)
        else:
            start_price = first.last

        if start_price is not None and last.last is not None:
            data[symbol]["price_diff"] = 100*(last.last - start_price) / start_price
        else:
            print(f"No last for {first} or {last} for {symbol}")

        try:
            data[symbol]["volume_correlation"] = calculate.volume_correlation(symbol_data)
        except TypeError:
            print(f"Error calculating volume correlation for {symbol}")
        try:
            data[symbol]["slope_correlation"] = calculate.slope_correlation(symbol_data)
        except TypeError:
            print(f"Error calculating slope correlation for {symbol}")

    # return sorted(data.values(), key=operator.itemgetter("price_diff"))
    return list(data.values())


def missing_minutes(symbol, day):
    existing_data = data_day(symbol.symbol, day)
    existing_minutes = set(existing_data.values_list("time", flat=True))

    trading_minutes = set(market.trading_minutes(day))

    missing = trading_minutes - existing_minutes

    return sorted(missing)


def missing_rolling_correlation_minutes(symbol, day, data_type):
    existing_data = rolling_correlation_data_day(symbol.symbol, day, data_type)
    existing_minutes = set(existing_data.values_list("time", flat=True))

    market_open, market_close = market.open_close(day)
    start = market_open + datetime.timedelta(minutes=ROLLING_CORRELATION_WINDOW) - market.ONE_MINUTE
    trading_minutes = set(minute for minute in market.trading_minutes(day)
                          if minute >= start)

    missing = trading_minutes - existing_minutes

    return sorted(missing)


def rolling_correlations_for_day(symbol_obj, day, data=None):
    rolls = []

    missing_volume = missing_rolling_correlation_minutes(symbol_obj, day, RollingCorrelation.DataType.VOLUME)
    missing_slope = missing_rolling_correlation_minutes(symbol_obj, day, RollingCorrelation.DataType.SLOPE)

    if not (missing_volume or missing_slope):
        return []

    if data is None:
        data = data_day(symbol_obj.symbol, day)

    for missing, data_type in ((missing_volume, RollingCorrelation.DataType.VOLUME), (missing_slope, RollingCorrelation.DataType.SLOPE)):

        for minute in missing:
            try:
                corr = calculate.rolling_correlation(minute, data, data_type, ROLLING_CORRELATION_WINDOW)
                if corr is None:
                    continue

                roll = RollingCorrelation(
                    time=minute,
                    symbol=symbol_obj,
                    data_type=data_type,
                    window=ROLLING_CORRELATION_WINDOW,
                    value=corr)

                rolls.append(roll)

            except (ValueError, TypeError) as e:
                pass

    return rolls


def market_holidays():
    api_data = api.market_holidays()
    for rec in api_data:
        rec["date"] = datetime.datetime.strptime(rec["date"], "%Y-%m-%d").date()
        if "open" in rec:
            rec["open"] = datetime.datetime.fromisoformat(rec["open"].replace("Z", "+00:00"))
        if "close" in rec:
            rec["close"] = datetime.datetime.fromisoformat(rec["close"].replace("Z", "+00:00"))

    return api_data


def new_market_holidays():
    api_data = market_holidays()
    existing_dates = set(MarketHoliday.objects.values_list("day", flat=True))
    new = [rec for rec in api_data if rec["date"] not in existing_dates]
    return new


def update_market_holidays():
    new_holidays = new_market_holidays()
    objs = []

    for holiday in new_holidays:
        h = MarketHoliday(
            day=holiday["date"],
            status=holiday["status"],
            exchange=holiday["exchange"],
            name=holiday["name"],
            open=holiday.get("open"),
            close=holiday.get("close"))
        h.save()
        objs.append(h)

    return objs


def holiday_for_day(day=None):
    if day is None:
        day = timezone.localdate()

    holidays = MarketHoliday.objects.filter(day=day, exchange="NYSE")
    return holidays[0] if holidays else None


def is_live_paused():
    return SystemSetting.objects.get(name="live_paused").value


def live_updates_start():
    ss = SystemSetting.objects.get(name="live_paused")
    ss.set_value(False)
    ss.save()


def live_updates_pause():
    ss = SystemSetting.objects.get(name="live_paused")
    ss.set_value(True)
    ss.save()
