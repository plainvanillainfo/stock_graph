import logging
import sys

from django.core.management.base import BaseCommand

import volume.backfill

LOG_FORMAT = "[%(asctime)s] %(levelname)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Set up logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format=LOG_FORMAT,
                    datefmt=LOG_DATE_FORMAT)


class Command(BaseCommand):
    help = "Processes uploaded files"

    def handle(self, *args, **kwargs):
        volume.backfill.run()

