import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

import volume.utils


@transaction.atomic
def delete_data(minutes, data_days, correlations):
    minutes.delete()
    data_days.delete()
    correlations.delete()


class Command(BaseCommand):
    help = "Delete data for one day"

    def add_arguments(self, parser):
        parser.add_argument("symbol")
        parser.add_argument("day")

    def handle(self, *args, **kwargs):
        day = datetime.datetime.strptime(kwargs["day"], "%Y-%m-%d")
        symbol = kwargs["symbol"]

        minutes, data_days, correlations = volume.utils.load_all_day_data(symbol, day)

        print(f"For {symbol}")
        print(f"Found {minutes.count()} Minutes")
        print(f"Found {data_days.count()} DataDays")
        print(f"Found {correlations.count()} Correlations")

        print("Type DELETE to confirm deletion")
        inp = input("> ")

        if inp != "DELETE":
            print("Aborting")
        else:
            print("Deleting")
            delete_data(minutes, data_days, correlations)
            print("Done")
