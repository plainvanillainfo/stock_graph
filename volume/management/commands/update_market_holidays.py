import datetime
import logging
import sys
import time

from django.core.management.base import BaseCommand

import volume.logic

LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Set up logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT,
                    datefmt=LOG_DATE_FORMAT)


class Command(BaseCommand):
    help = "Update market holidays"

    def handle(self, *args, **kwargs):
        added = volume.logic.update_market_holidays()
        for mh in added:
            logging.info(f"Added {mh}")

