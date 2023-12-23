import datetime

from django.core.management.base import BaseCommand

import volume.utils


class Command(BaseCommand):
    help = "Backfill all symbols for a day"

    def add_arguments(self, parser):
        parser.add_argument("day")

    def handle(self, *args, **kwargs):
        day = datetime.datetime.strptime(kwargs["day"], "%Y-%m-%d")
        count = volume.utils.backfill_all_symbols_for_day(day)
        print(f"Queued {count} days")
