import concurrent.futures
import datetime
import functools
import itertools
import logging
import threading
from collections import defaultdict

from django.utils import timezone

from . import api
from . import calculate
from . import logic
from . import market
from . import ws
from .models import Symbol, Minute, DataDay, MinuteData, IndexWeight, IncomingPrice, Correlation, Group, RollingCorrelation


NUM_THREADS = 6

CORRELATION_MINIMUM_DATA_POINTS_BEFORE_SEND = 15


class TooOld(Exception):
    pass


def get_or_create_dataday(symbol, day):
    try:
        dataday = DataDay.objects.get(symbol=symbol, day=day)
    except DataDay.DoesNotExist:
        dataday = DataDay(symbol=symbol, day=day, state=DataDay.State.LIVE)
        dataday.save()

    return dataday


def day_complete(symbol, day):
    existing_data = logic.data_day(symbol.symbol, day)
    return existing_data.count() == market.count_minutes_in_trading_day()


def incoming_data(symbol, minute, symbol_obj=None):

    if market.is_opening_minute(minute):
        cumulative_volume = 0
        cumulative_slope = 0
        if symbol_obj and symbol_obj.is_index:
            last_mid = 0
        else:
            last_mid = api.mid_last(symbol, minute)
        write_back = symbol_obj is None

    elif symbol_obj is not None:
        write_back = False
        try:
            last = logic.minute_before(symbol, minute)
            last_mid = last.last_mid_before
            cumulative_volume = last.cumulative_volume
            cumulative_slope = last.slope

            if cumulative_volume is None:
                raise ValueError

        except Minute.DoesNotExist:
            logging.error(f"Last minute DNE for {symbol.symbol} at {minute}")
            raise ValueError

    else:
        write_back = True
        cumulative_volume = 0
        cumulative_slope = 0
        incoming = logic.incoming_price_for(symbol, minute)
        if incoming is not None:
            last_mid = incoming.last_mid_before
        else:
            last_mid = api.mid_last(symbol, minute)

    return cumulative_volume, last_mid, cumulative_slope, write_back


@functools.lru_cache(maxsize=250)
def stock_for_minute(symbol, minute, symbol_obj=None):

    cumulative_volume, last_mid, cumulative_slope, write_back = incoming_data(symbol, minute, symbol_obj)

    trade = api.trade_minute(symbol, minute)
    quote = api.quote_minute(symbol, minute)

    volume, last_mid = calculate.calculate(quote, trade, last_mid)
    cumulative_volume += volume
    last = calculate.last_price(trade)
    slope = calculate.calculate_slope(volume)
    cumulative_slope += slope

    logging.info(f"{symbol}\t{minute}\t{volume}\t{cumulative_volume}\t{last_mid}\t{slope}\t{cumulative_slope}")

    if write_back:
        IncomingPrice.objects.create(symbol=symbol, time=minute, last_mid_before=last_mid)

    return MinuteData(minute, symbol, last, volume, cumulative_volume, last_mid, cumulative_slope)


def index_for_minute(symbol, minute, existing, executor, symbol_obj):
    cumulative_volume, _, cumulative_slope, _ = incoming_data(symbol, minute, symbol_obj)

    weights = logic.weights(symbol_obj)
    all_symbols = set(weights.keys())
    existing_set = set(existing.keys())
    needed = all_symbols - existing_set

    futures = []
    for symbol in needed:
        fut = executor.submit(stock_for_minute, symbol, minute)
        futures.append(fut)

    for future in concurrent.futures.as_completed(futures):
        minute_data = future.result()
        existing[minute_data.symbol] = minute_data

    volume = calculate.weighted_volume(weights, existing)
    cumulative_volume += volume
    slope = calculate.calculate_slope(volume)
    cumulative_slope += slope

    last = api.index_value(symbol_obj.api_symbol, minute)
    if not last:
        logging.warning(f"No index value for {symbol_obj.name}")

    return MinuteData(minute, symbol, last, volume, cumulative_volume, None, cumulative_slope)


def run_for_symbol(symbol, existing, executor, day=None, limit=None):
    symbol_data = defaultdict(dict)

    if day is None:
        day = timezone.localdate()

    dataday = get_or_create_dataday(symbol, day)
    missing = logic.missing_minutes(symbol, day)
    if limit is not None:
        missing = missing[:limit]

    for minute in missing:
        if symbol.type == Symbol.Type.STOCK:
            minute_data = stock_for_minute(symbol.symbol, minute, symbol)
            minute_obj = Minute.from_minute_data(minute_data, symbol)
            symbol_data[minute][symbol.symbol] = minute_obj

        elif symbol.type == Symbol.Type.INDEX:
            minute_data = index_for_minute(symbol.symbol,
                                           minute,
                                           existing[minute],
                                           executor,
                                           symbol)
            minute_obj = Minute.from_minute_data(minute_data, symbol)
            symbol_data[minute][symbol.symbol] = minute_obj

        minute_obj.save()
        ws.send_minute(minute_obj)

        if market.is_closing_minute(minute) and day_complete(symbol, day):
            dataday.state = DataDay.State.COMPLETE
            dataday.save()

    return symbol_data


def missing_index_minutes(index, day=None):
    if day is None:
        day = timezone.localdate()

    return logic.missing_minutes(index, day)


def index_db_data_for_minute(index, minute):
    index_symbols = index.weights.values_list("symbol", flat=True)
    minutes = Minute.objects.filter(symbol__symbol__in=index_symbols, time=minute)
    return minutes


def update_data(all_data, update):
    for minute, minute_data in update.items():
        all_data[minute].update(minute_data)


def update_rolling_correlations(symbol_obj, day, data_type):
    missing = logic.missing_rolling_correlation_minutes(symbol_obj, day, data_type)
    if not missing:
        return
    earliest = missing[0]
    _, end = logic.day_to_range(day)
    start = earliest - logic.ROLLING_CORRELATION_INTERVAL

    data = Minute.timescale.filter(symbol=symbol_obj, time__range=(start, end))

    for minute in missing:
        try:
            corr = calculate.rolling_correlation(minute, data, data_type, logic.ROLLING_CORRELATION_WINDOW)
        except (TypeError, ValueError):
            corr = None
            # logging.warning(f"Problem calculating rolling correlations for {symbol_obj.symbol}")
        if corr is None:
            continue

        roll = RollingCorrelation(
            time=minute,
            symbol=symbol_obj,
            data_type=data_type,
            window=logic.ROLLING_CORRELATION_WINDOW,
            value=corr)

        roll.save()
        ws.send_rolling_correlation(roll)


def update_correlations(symbol_data, day, data_type):
    corr = Correlation.objects.filter(day=day, data_type=data_type).select_related("symbol")
    corr_objs = {c.symbol.symbol: c for c in corr}
    new_objs = []

    for minute, minute_data in symbol_data.items():
        for symbol, minute_obj in minute_data.items():
            if data_type == Correlation.DataType.VOLUME:
                y = minute_obj.cumulative_volume
            elif data_type == Correlation.DataType.SLOPE:
                y = minute_obj.slope

            if minute_obj.last is None or y is None:
                continue

            if symbol not in corr_objs:
                try:
                    symbol_obj = Symbol.objects.get(symbol=symbol)
                except Symbol.DoesNotExist:
                    continue

                corr_objs[symbol] = Correlation(symbol=symbol_obj,
                                                day=day,
                                                data_type=data_type,
                                                x_mean=0,
                                                y_mean=0,
                                                N=0,
                                                D=0,
                                                E=0,
                                                n=0)
                new_objs.append(corr_objs[symbol])

            calculate.update_online_correlation(corr_objs[symbol], minute_obj.last, y)

    if new_objs:
        Correlation.objects.bulk_create(new_objs)

    to_update = [co for co in corr_objs.values() if co.value is not None]
    Correlation.objects.bulk_update(to_update,
        ["x_mean", "y_mean", "N", "D", "E", "value", "n"])

    to_send = [co for co in corr_objs.values() if co.n >= CORRELATION_MINIMUM_DATA_POINTS_BEFORE_SEND]

    if to_send:
        push_correlations(to_send, data_type)


def push_correlations(corr_objs, data_type):
    # Send all
    ws.send_correlations("all", corr_objs, data_type)

    # Send groups
    groups = Group.objects.filter(group_type=Group.GroupType.CORRELATION_TABLE).prefetch_related("symbols")
    for group in groups:
        group_symbols = set(group.symbols.values_list("symbol", flat=True))
        to_send = [co for co in corr_objs if co.symbol.symbol in group_symbols]
        ws.send_correlations(group.slug, to_send, data_type)


def push_slope_tables():
    # Send all
    ws.send_slope_table(None)

    # Send groups
    groups = Group.objects.filter(group_type=Group.GroupType.SLOPE_TABLE).prefetch_related("symbols")
    for group in groups:
        ws.send_slope_table(group)


def run(day=None, limit=None, threads=None, skip_indices=False):
    if day is None:
        day = timezone.localdate()

    stocks = Symbol.objects.stocks(active=True)
    if skip_indices:
        indices = []
    else:
        indices = Symbol.objects.indices(active=True)

    all_data = defaultdict(dict)

    if threads is None:
        threads = NUM_THREADS

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:

        # Stocks
        logging.info("Getting %d stocks", stocks.count())

        futures = []
        for symbol in stocks:
            fut = executor.submit(run_for_symbol, symbol, all_data, executor, day, limit)
            futures.append(fut)

        for future in concurrent.futures.as_completed(futures):
            try:
                symbol_data = future.result()
                update_data(all_data, symbol_data)

            except Exception:
                logging.exception(f"Exception resolving future")

        # Indices
        if indices:
            logging.info("Getting %d indices", indices.count())

        for index in indices:
            index_data = run_for_symbol(index, all_data, executor, day, limit=limit)
            update_data(all_data, index_data)

        # Update correlations
        if all_data:
            for symbol_obj in itertools.chain(stocks, indices):
                update_rolling_correlations(symbol_obj, day, RollingCorrelation.DataType.VOLUME)
                update_rolling_correlations(symbol_obj, day, RollingCorrelation.DataType.SLOPE)

            update_correlations(all_data, day, Correlation.DataType.VOLUME)
            update_correlations(all_data, day, Correlation.DataType.SLOPE)
            push_slope_tables()


    logging.info("Done")
