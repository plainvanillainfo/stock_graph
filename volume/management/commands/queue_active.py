from django.core.management.base import BaseCommand

import volume.logic


class Command(BaseCommand):
    help = "Queue backfill days for all active symbols"

    def handle(self, *args, **kwargs):
        count = volume.logic.queue_active_symbols()
        print(f"Queued {count} days")
