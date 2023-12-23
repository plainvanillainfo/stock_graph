import functools
import json
from decimal import Decimal

import requests
from bs4 import BeautifulSoup


USER_AGENT = "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:96.0) Gecko/20100101 Firefox/96.0"
headers = {
    "User-Agent": USER_AGENT,
}
BASE_URL = "https://www.slickcharts.com"
TIMEOUT = 10


def scrape_slickcharts(path):
    r = requests.get(BASE_URL + "/" + path, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table", class_="table-borderless")
    rows = table.find("tbody").find_all("tr")

    return {row[2].text.strip(): Decimal(row[3].text.strip())/100
            for tr in rows
            if (row := tr.find_all("td"))}


scrape_dowjones = functools.partial(scrape_slickcharts, "dowjones")
scrape_nasdaq = functools.partial(scrape_slickcharts, "nasdaq100")


def scrape_yahoo(symbol):
    BASE_URL = "https://finance.yahoo.com/quote/"
    r = requests.get(BASE_URL + symbol, headers=headers, timeout=TIMEOUT)

    if not "QuoteSummaryStore" in r.text:
        raise ValueError

    json_str = r.text.split("root.App.main =")[1].split(
        "(this)")[0].split(";\n")[0].strip()
    data = json.loads(json_str)["context"]["dispatcher"]["stores"]["QuoteSummaryStore"]
    return data["price"]["regularMarketPrice"]["raw"]


yahoo_dowjones = functools.partial(scrape_yahoo, "^DJI")
yahoo_nasdaq = functools.partial(scrape_yahoo, "^IXIC")
