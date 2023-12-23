import datetime

import requests

API_KEY = "nXg2TNrbpoMlitbcI0p8iJk1ku1QtKla"
BASE_URL = "https://api.polygon.io"


def to_nanos(dt):
    return int(dt.timestamp()) * 10**9


def calc_mid(quote):
    return (quote["bid_price"] + quote["ask_price"]) / 2


def api_request(endpoint, params):
    now = datetime.datetime.now()
    url = BASE_URL + endpoint
    params["apiKey"] = API_KEY
    r = requests.get(url, params=params)
    r.raise_for_status()
    assert r.json()["status"] == "OK"
    print(f"{now:%T}\t{endpoint}\t{r.elapsed.total_seconds():.2f}")
    return r.json()["results"]


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
    params = {
        "timestamp.lt": to_nanos(time),
        "sort": "timestamp",
        "order": "desc",
        "limit": 1,
    }

    results = api_request("/vX/quotes/" + symbol, params)
    result = results[0]
    return calc_mid(result) 
