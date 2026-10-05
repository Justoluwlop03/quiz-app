import random


def shuffle_choices(options, rng=None):
    choices = list(options)
    (rng or random).shuffle(choices)
    return choices


def seconds_remaining(deadline, now):
    """Return a nonnegative integer countdown based on absolute timestamps."""
    return max(0, int(deadline - now))
