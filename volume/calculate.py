import csv
import datetime
import math

import numpy

from .models import RollingCorrelation


def calc_mid(quote):
    return (quote["bid_price"] + quote["ask_price"]) / 2


def weighted_volume(weights, values):
    volume = 0
    for symbol, weight in weights.items():
        minute = values[symbol]
        volume += (minute.volume * float(weight))

    return volume


def calculate(quotes, trades, mid):
    total_volume = 0
    # print(len(quote_response.json()["results"]))

    if quotes:
        last_mid = calc_mid(quotes[-1])
        quotes = iter(quotes)
        next_quote = next(quotes)
        next_time = next_quote["sip_timestamp"]
    else:
        last_mid = mid

    for trade in trades:

        if "size" not in trade:
            # A fictitious trade
            continue

        trade_time = trade["sip_timestamp"]
        # print(f"\t\t{trade_time}")

        if quotes:
            while next_quote is not None and next_time <= trade_time:
                try:
                    next_mid = calc_mid(next_quote)
                    quote = next_quote
                    quote_time = next_time
                    mid = next_mid
                    # print(f"Skip to \t{quote_time}")

                except KeyError:
                    # Either bid or ask is missing
                    pass

                try:
                    next_quote = next(quotes)
                    next_time = next_quote["sip_timestamp"]
                except StopIteration:
                    next_quote = None
                # print("End of quotes")

        # assert quote_time <= trade_time
        # assert next_time > trade_time

        trade_price = trade["price"]
        volume = int(trade["size"])

        if trade_price > mid:
            total_volume += volume
        elif trade_price < mid:
            total_volume -= volume

    return total_volume, last_mid


def last_price(trades):
    if trades:
        return trades[-1]["price"]
    else:
        return None


def write_csv(results, filename):
    with open(filename, "w") as f:
        writer = csv.writer(f)
        writer.writerow(["Minute UTC", "Last Trade", "Minute Volume", "Daily Volume"])
        for res in results:
            writer.writerow([
                res["datetime_utc"],
                res["last"],
                res["volume"],
                res["cumulative_volume"]
            ])


def calculate_slope(minute_volume):
    if minute_volume is None:
        return 0

    if minute_volume > 0:
        return 1
    elif minute_volume < 0:
        return -1
    else:
        return 0


def correlation(a, b):
    return numpy.corrcoef(a, b)[0, 1]


def volume_correlation(day_data):
    prices = [float(d.last) for d in day_data]
    volumes = [float(d.cumulative_volume) for d in day_data]

    if not prices or not volumes:
        raise ValueError

    return correlation(prices, volumes)


def slope_correlation(day_data):
    prices = [float(d.last) for d in day_data]
    slopes = [d.slope for d in day_data]

    if not prices or not slopes:
        raise ValueError

    return correlation(prices, slopes)


def update_online_correlation(correlation, x, y):
    if x is None or y is None:
        return

    x_mean = correlation.x_mean + (x - correlation.x_mean) / (correlation.n + 1)
    y_mean = correlation.y_mean + (y - correlation.y_mean) / (correlation.n + 1)

    N = correlation.N + (x - correlation.x_mean)*(y - y_mean)
    D = correlation.D + (x - correlation.x_mean)*(x - x_mean)
    E = correlation.E + (y - correlation.y_mean)*(y - y_mean)

    denominator = math.sqrt(D)*math.sqrt(E)
    r = N / denominator if denominator != 0 else 0

    correlation.x_mean = x_mean
    correlation.y_mean = y_mean
    correlation.N = N
    correlation.D = D
    correlation.E = E
    correlation.value = r
    correlation.n += 1


def rolling_correlation(minute, data, data_type, window):
    window_interval = datetime.timedelta(minutes=window)
    start = minute - window_interval
    rolling_data = [m for m in data if start < m.time <= minute]

    if len(rolling_data) != window:
        return None

    prices = [float(m.last) for m in rolling_data]
    if data_type == RollingCorrelation.DataType.VOLUME:
        values = [float(m.cumulative_volume) for m in rolling_data]
    else:
        values = [m.slope for m in rolling_data]

    return correlation(prices, values)
