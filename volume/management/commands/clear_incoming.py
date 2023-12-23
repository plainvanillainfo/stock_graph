import datetime
import logging
import sys
import time

from django.core.management.base import BaseCommand

import volume.logic


class Command(BaseCommand):
    help = "Clear IncomingPrice data from DB"

    def handle(self, *args, **kwargs):
        volume.logic.clear_incoming_prices()

