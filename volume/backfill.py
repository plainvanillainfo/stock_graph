import concurrent.futures
import datetime
import logging
import time

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from . import api
from . import calculate
from . import logic
from . import market
from .models import Symbol, Minute, DataDay, MinuteData, RollingCorrelation


SLEEP_TIME = datetime.timedelta(seconds=5)
RETRY_WAIT_TIME = datetime.timedelta(minutes=15)

NUM_THREADS = 10
NUM_INDEX_THREADS = 10



def get_day_data(symbols, day):
    all_results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_INDEX_THREADS) as executor:
        futures = []
        for symbol in symbols:
            fut = executor.submit(raw_stock_day_data_with_symbol, symbol, day)
            futures.append(fut)

        for future in concurrent.futures.as_completed(futures):
            symbol, results = future.result()
            all_results[symbol] = results

    return all_results


def raw_stock_day_data_with_symbol(symbol, day):
    return symbol, raw_stock_day_data(symbol, day)


def raw_stock_day_data(symbol, day):
    results = []
    cumulative_volume = 0
    cumulative_slope = 0

    last_mid = None
    previous_last = None

    for dt in market.all_trading_minutes(day):
        if last_mid is None:
            last_mid = api.mid_last(symbol, dt)

        trade = api.trade_minute(symbol, dt)
        quote = api.quote_minute(symbol, dt)

        volume, last_mid = calculate.calculate(quote, trade, last_mid)
        cumulative_volume += volume
        last = calculate.last_price(trade)
        if last is None:
            last = previous_last
        else:
            previous_last = last

        slope = calculate.calculate_slope(volume)
        cumulative_slope += slope

        # logging.info(f"{symbol}\t{dt}\t{volume}\t{cumulative_volume}\t{last_mid}\t{slope}\t{cumulative_slope}")

        results.append(MinuteData(dt, symbol, last, volume, cumulative_volume, last_mid, cumulative_slope))

    return results


def stock_day_data(symbol, day):
    data = raw_stock_day_data(symbol.symbol, day)
    return [Minute.from_minute_data(elem, symbol) for elem in data]


def calculate_index_minutes(symbol_obj, weights, values, day):
    results = []
    cumulative_volume = 0
    cumulative_slope = 0

    for i, dt in enumerate(market.all_trading_minutes(day)):
        volume = 0
        for symbol, weight in weights.items():
            minute = values[symbol][i]
            assert minute.time == dt
            volume += (minute.volume * weight)

        cumulative_volume += volume
        slope = calculate.calculate_slope(volume)
        cumulative_slope += slope

        m = Minute(
            time=dt,
            symbol=symbol_obj,
            volume=volume,
            cumulative_volume=cumulative_volume,
            slope=cumulative_slope)

        results.append(m)

    return results


def add_index_values(index_data, symbol_obj, day):
    logging.info("Get day index values")
    day_values = api.index_values_for_day(symbol_obj.api_symbol, day)
    day_value_dict = {m: v for m, v in day_values}

    new_values = []
    for minute_obj in index_data:
        value = day_value_dict.get(minute_obj.time)
        source = "D"
        if value is None:
            value = api.index_value(minute_obj.symbol.api_symbol, minute_obj.time)
            source = "A"

        # if value is not None:
        #     logging.info(f"{minute_obj.symbol.symbol}\t{minute_obj.time}\t{source}\t{value:.2f}")
        # else:
        #     logging.info(f"{minute_obj.symbol.symbol}\t{minute_obj.time}\t{source}\tNone")

        minute_obj.last = value
        new_values.append(minute_obj)

    return new_values


def index_day_data(symbol_obj, day):
    weights = logic.weights(symbol_obj)
    all_symbols = set(weights.keys())

    existing = DataDay.objects.filter(symbol__symbol__in=all_symbols, day=day, state=DataDay.State.COMPLETE)
    existing_set = set(dataday.symbol.symbol for dataday in existing)
    needed = all_symbols - existing_set

    new_values = get_day_data(needed, day)

    for symbol in existing_set:
        logging.info(f"DB get {symbol}")
        new_values[symbol] = logic.data_day(symbol, day)

    assert set(new_values.keys()) == all_symbols

    index_data = calculate_index_minutes(symbol_obj, weights, new_values, day)
    index_data = add_index_values(index_data, symbol_obj, day)
    return index_data


def day_data(symbol, day):
    if symbol.type == Symbol.Type.STOCK:
        data = stock_day_data(symbol, day)
    elif symbol.type == Symbol.Type.INDEX:
        data = index_day_data(symbol, day)

    rolling_correlations = logic.rolling_correlations_for_day(symbol, day, data)

    try:
        volume_correlation, slope_correlation = logic.correlation_objects(symbol, day, data)
        return data, [volume_correlation, slope_correlation], rolling_correlations
    except (TypeError, ValueError):
        return data, [], rolling_correlations



@transaction.atomic
def store_day_data(day, data, correlation_objects, rolling_correlations):
    day.state = DataDay.State.COMPLETE
    day.last_tried = None
    day.save()
    Minute.objects.bulk_create(data)
    RollingCorrelation.objects.bulk_create(rolling_correlations)
    for corr in correlation_objects:
        corr.save()


def load_data_for_day(day_object):
    data, correlation_objects, rolling_correlations = day_data(day_object.symbol, day_object.day)
    store_day_data(day_object, data, correlation_objects, rolling_correlations)



def get_outstanding_days(symbol_type=None):
    retry_before = timezone.now() - RETRY_WAIT_TIME
    days_to_get = DataDay.objects.filter(state=DataDay.State.PENDING)
    if symbol_type is not None:
        days_to_get = days_to_get.filter(symbol__type=symbol_type)
    days_to_get = days_to_get.filter(Q(last_tried__lte=retry_before) | Q(last_tried__isnull=True))
    days_to_get = days_to_get.order_by(F("last_tried").asc(nulls_first=True))
    return days_to_get


def get_day(day):
    logging.info(f"Getting {day}")
    try:
        load_data_for_day(day)
        logging.info(f"Got {day}")
    except Exception:
        logging.exception(f"Exception getting {day}")
        day.last_tried = timezone.now()
        day.save()


def update_outstanding_days_parallel(days_to_get):

    with concurrent.futures.ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        for day in days_to_get:
            executor.submit(get_day, day)


def update_outstanding_days(days_to_get):

    if days_to_get:
        logging.info(f"Pending: {len(days_to_get)} days")

    for day in days_to_get:
        get_day(day)


def run():
    while True:
        stocks_to_get = get_outstanding_days(Symbol.Type.STOCK)
        indices_to_get = get_outstanding_days(Symbol.Type.INDEX)

        if stocks_to_get or indices_to_get:
            logging.info(f"Pending: {len(stocks_to_get)} stocks")
            update_outstanding_days_parallel(stocks_to_get)

            logging.info(f"Pending: {len(indices_to_get)} indices")
            update_outstanding_days_parallel(indices_to_get)

        else:
            time.sleep(SLEEP_TIME.total_seconds())


if __name__ == "__main__":
    run()
