import datetime
import logging
import sys
import time

from django.core.management.base import BaseCommand

import volume.weights

SLEEP_TIME = datetime.timedelta(seconds=2)  # Wait this much time for data to settle

LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Set up logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT,
                    datefmt=LOG_DATE_FORMAT)


class Command(BaseCommand):
    help = "Update weights for indices"

    def handle(self, *args, **kwargs):
        volume.weights.update_all()

