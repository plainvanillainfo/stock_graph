import csv
import datetime
import sys
from pathlib import Path

from . import api
from . import market


TRADE_HEADER = ["Symbol", "Date", "Time", "Volume", "Price"]
QUOTE_HEADER = ["Symbol", "Date", "Time", "Bid", "Bid Size", "Ask", "Ask Size"]


def format_quote_row(symbol, data):
    dt = datetime.datetime.fromtimestamp(data["sip_timestamp"] / 1e9)
    return (
        symbol,
        dt.strftime("%F"),
        dt.strftime("%T.%f"),
        data.get("bid_price"),
        data.get("bid_size"),
        data.get("ask_price"),
        data.get("ask_size"),
    )


def format_trade_row(symbol, data):
    dt = datetime.datetime.fromtimestamp(data["sip_timestamp"] / 1e9)
    return (
        symbol,
        dt.strftime("%F"),
        dt.strftime("%T.%f"),
        data.get("size"),
        data.get("price"),
    )


def write_csv(gen, header, filename):
    with filename.open("w") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(gen)


def data_generate(symbol, day, api_func, format_func):
    for minute in market.all_trading_minutes(day):
        print(minute)
        data = api_func(symbol, minute)
        for row in data:
            yield format_func(symbol, row)


def run_quote(symbol, day):
    filename = f"{symbol} {day:%F} Raw Quote.csv"
    write_csv(data_generate(symbol, day, api.quote_minute, format_quote_row),
              QUOTE_HEADER,
              Path(filename))


def run_trade(symbol, day):
    filename = f"{symbol} {day:%F} Raw Trade.csv"
    write_csv(data_generate(symbol, day, api.trade_minute, format_trade_row),
              TRADE_HEADER,
              Path(filename))


if __name__ == "__main__":
    symbol = sys.argv[1]
    day = datetime.date(*[int(sys.argv[i]) for i in range(2, 5)])
    run(symbol, day)

