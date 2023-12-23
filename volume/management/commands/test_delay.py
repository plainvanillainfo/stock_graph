import datetime
import logging
import sys
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

import volume.api as api

LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MINUTE = datetime.timedelta(minutes=1)
SYMBOL = "I:NDX"

# Set up logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT,
                    datefmt=LOG_DATE_FORMAT)


class Command(BaseCommand):
    help = "Test delayed index price data"

    def handle(self, *args, **kwargs):
        now = timezone.now()
        print(f"Current time: {now:%F %T}")

        minute_start = now.replace(second=0, microsecond=0)

        i = 0
        while True:
            i += 1
            t = minute_start - i*MINUTE
            ago = now - t
            mins = ago.total_seconds() // 60
            secs = ago.total_seconds() % 60
            result = api.index_value(SYMBOL, t)
            out = "Data available" if result else "No data"
            print(f"For {t:%F %T} [{mins:.0f}m{secs:.0f}s ago] {out}")
            if result:
                break




