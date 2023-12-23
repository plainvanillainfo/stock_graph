import datetime
import pickle
from pathlib import Path

import scrape

DIRECTORY = "weights"

INDICES = {
    "nasdaq": scrape.scrape_nasdaq,
    "dowjones": scrape.scrape_dowjones,
}


def today_filename(index):
    return Path(DIRECTORY) / (index + "_" + datetime.datetime.now().strftime("%F") + ".p")


def run():
    for name, func in INDICES.items():
        with today_filename(name).open("wb") as f:
            data = func()
            pickle.dump(data, f, pickle.HIGHEST_PROTOCOL)


if __name__ == "__main__":
    run()
