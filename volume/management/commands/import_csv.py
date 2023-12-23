from pathlib import Path

from django.core.management.base import BaseCommand

import volume.csv_import


class Command(BaseCommand):
    help = "Import CSVs"

    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    def handle(self, *args, **kwargs):
        csv_path = Path(kwargs["csv_path"])
        min_count, day_count = volume.csv_import.process_csv(csv_path)

        print(f"Added {min_count} minutes on {day_count} datadays")
