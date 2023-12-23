import logging

import requests

from django.utils import timezone

from . import views
from .models import RollingCorrelation


URL = "http://localhost:8081/pub"
TIMEOUT = 5
CHART_DATETIME_FORMAT = "%F %T"


def push_html_to_ws(channel, html):
    params = {"channel": channel}
    r = requests.post(URL, params=params, data=html, timeout=TIMEOUT)
    return r.ok


def push_to_ws(channel, data):
    params = {"channel": channel}
    r = requests.post(URL, params=params, json=data, timeout=TIMEOUT)
    return r.ok


def send_for_all(minute):
    tz = timezone.get_current_timezone()
    data = {
        "all": True,
        "plot_name": minute.symbol.symbol,
        "datetime": minute.time.astimezone(tz).strftime(CHART_DATETIME_FORMAT),
        "volume": minute.cumulative_volume,
        "slope": minute.slope,
    }
    push_to_ws("all", data)


def send_for_symbol(minute):
    tz = timezone.get_current_timezone()
    channel = f"stock_{minute.symbol.symbol}"
    volume_data = {
        "all": False,
        "plot_name": "Volume",
        "datetime": minute.time.astimezone(tz).strftime(CHART_DATETIME_FORMAT),
        "value": minute.cumulative_volume,
    }
    push_to_ws(channel, volume_data)

    slope_data = {
        "all": False,
        "plot_name": "Slope",
        "datetime": minute.time.astimezone(tz).strftime(CHART_DATETIME_FORMAT),
        "value": minute.slope,
    }
    push_to_ws(channel, slope_data)

    price_data = {
        "all": False,
        "plot_name": "Price",
        "datetime": minute.time.astimezone(tz).strftime(CHART_DATETIME_FORMAT),
        "value": minute.last,
    }
    push_to_ws(channel, price_data)


def send_rolling_correlation(roll):
    tz = timezone.get_current_timezone()
    channel = f"stock_{roll.symbol.symbol}"

    plot_name = "Volume" if roll.data_type == RollingCorrelation.DataType.VOLUME else "Slope"
    plot_name += f" Correlation ({roll.window}m)"

    roll_data = {
        "all": False,
        "plot_name": plot_name,
        "datetime": roll.time.astimezone(tz).strftime(CHART_DATETIME_FORMAT),
        "value": roll.value,
    }

    push_to_ws(channel, roll_data)


def send_minute(minute):
    try:
        send_for_all(minute)
        send_for_symbol(minute)
    except Exception:
        logging.exception("Exception sending to websocket")


def send_correlations(slug, correlations, data_type):
    html = views.correlation_partial_table(correlations, data_type)
    try:
        push_html_to_ws(f"correlations_{slug}", html)
    except Exception:
        logging.exception("Exception sending to websocket")


def send_slope_table(group):
    if group is None:
        slug = "all"
    else:
        slug = group.slug
    html = views.slope_partial_table(group)
    try:
        push_html_to_ws(f"slope_table_{slug}", html)
    except Exception:
        logging.exception("Exception sending to websocket")
