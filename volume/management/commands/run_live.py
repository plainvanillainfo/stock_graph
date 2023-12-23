import datetime
import logging
import sys
import time

from django.core.management.base import BaseCommand

import volume.live
import volume.logic

# SLEEP_TIME = datetime.timedelta(seconds=2)  # Wait this much time for data to settle

LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Set up logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT,
                    datefmt=LOG_DATE_FORMAT)


class Command(BaseCommand):
    help = "Runs live updates"

    def handle(self, *args, **kwargs):
        # time.sleep(SLEEP_TIME.total_seconds())
        if not volume.logic.is_live_paused():
            volume.live.run()

