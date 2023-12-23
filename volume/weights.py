import logging

from django.db import transaction

from . import scrape
from . import logic
from .models import IndexWeight, Symbol


SCRAPE_FUNCTIONS = {
    "nasdaq": scrape.scrape_nasdaq,
    "dow-jones": scrape.scrape_dowjones,
}


class NoWeights(Exception):
    pass


@transaction.atomic
def update_weights(index):
    current_weights = {weight.symbol: weight
                       for weight in index.weights.all()}
    new_weights = SCRAPE_FUNCTIONS[index.symbol]()

    logging.info(f"For {index}: {len(current_weights)} current weights, {len(new_weights)} new weights")

    if not new_weights:
        raise NoWeights

    current_set = set(current_weights.keys())
    new_set = set(new_weights.keys())

    added = new_set - current_set
    removed = current_set - new_set
    same = new_set & current_set

    for symbol in added:
        logging.info(f"Adding new symbol to {index}: {symbol} weight={new_weights[symbol]}")
        w = IndexWeight(index=index, symbol=symbol, weight=new_weights[symbol])
        w.save()

    for symbol in removed:
        logging.info(f"Removing symbol {symbol} from {index}")
        w = IndexWeight.objects.get(index=index, symbol=symbol)
        w.delete()

    for symbol in same:
        if current_weights[symbol].weight != new_weights[symbol]:
            logging.info(f"Updating weight for {symbol} in {index}: {current_weights[symbol].weight} -> {new_weights[symbol]}")
            w = current_weights[symbol]
            w.weight = new_weights[symbol]
            w.save()


def update_all():
    indices = Symbol.objects.indices().prefetch_related("weights")
    for index in indices:
        update_weights(index)
