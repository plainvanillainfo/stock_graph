import datetime

import requests

from django.utils import timezone

from . import market

API_KEY = "nXg2TNrbpoMlitbcI0p8iJk1ku1QtKla"
BASE_URL = "https://api.polygon.io"

TIMEOUT = 20


def to_nanos(dt):
    return int(dt.timestamp()) * 10**9


def to_millis(dt):
    return int(dt.timestamp()) * 10**3


def calc_mid(quote):
    return (quote["bid_price"] + quote["ask_price"]) / 2


def base_api_request(endpoint, params, raise_for_status=True):
    url = BASE_URL + endpoint
    params["apiKey"] = API_KEY
    r = requests.get(url, params=params, timeout=TIMEOUT)
    if raise_for_status:
        r.raise_for_status()
    return r.json()


def api_request(endpoint, params, follow_cursor=False):
    r_json = base_api_request(endpoint, params)
    assert r_json["status"] == "OK"
    results = r_json.get("results", [])

    if follow_cursor:
        while (next_url := r_json.get("next_url")):
            r = requests.get(next_url, params={"apiKey": API_KEY}, timeout=TIMEOUT)
            r.raise_for_status()
            assert r.json()["status"] == "OK"
            results += r.json()["results"]

    return results


def index_values(index_api_symbol, start, end):
    start_millis = to_millis(start)
    end_millis = to_millis(end)
    url = f"/v2/aggs/ticker/{index_api_symbol}/range/1/minute/{start_millis}/{end_millis}"
    params = {"sort": "asc"}
    results = api_request(url, params)
    return results


def index_value(index_api_symbol, minute):
    end = minute + datetime.timedelta(minutes=1)
    results = index_values(index_api_symbol, minute, end)

    if not results:
        return None

    res = results[0]
    return res["c"]


def index_values_for_day(index_api_symbol, day):
    market_open, market_close = market.open_close(day)
    results = index_values(index_api_symbol, market_open, market_close)

    return [(timezone.make_aware(datetime.datetime.fromtimestamp(r["t"] // 1000)), r["c"]) for r in results]



def trade_minute(symbol, minute):
    end = minute + datetime.timedelta(minutes=1)
    params = {
        "timestamp.gte": to_nanos(minute),
        "timestamp.lt": to_nanos(end),
        "sort": "timestamp",
        "order": "asc",
        "limit": 50000,
    }

    return api_request("/v3/trades/" + symbol, params)


def quote_minute(symbol, minute):
    end = minute + datetime.timedelta(minutes=1)
    params = {
        "timestamp.gte": to_nanos(minute),
        "timestamp.lt": to_nanos(end),
        "sort": "timestamp",
        "order": "asc",
        "limit": 50000,
    }

    return api_request("/vX/quotes/" + symbol, params)


def mid_last(symbol, time):
    timestamp_ns = to_nanos(time)
    result = {}
    required = ("bid_price", "ask_price")
    while not all(key in result for key in required):
        params = {
            "timestamp.lt": timestamp_ns,
            "sort": "timestamp",
            "order": "desc",
            "limit": 1,
        }

        results = api_request("/vX/quotes/" + symbol, params)
        result = results[0]
        timestamp_ns= result["sip_timestamp"]

    return calc_mid(result)


def verify_symbol(symbol):
    params = {
        "ticker": symbol,
        "market": "stocks",
    }

    result = api_request("/v3/reference/tickers", params)
    return result[0] if result else None


def market_holidays():
    return base_api_request("/v1/marketstatus/upcoming", {})
