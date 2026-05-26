"""
Custom Pydantic-compatible annotated types.

``Duration``
    A float representing seconds, parsed from human-readable strings such as
    ``100ms``, ``1s``, ``2m``, ``1.5h``.  Bare numbers are accepted as-is and
    treated as seconds.
"""

import re
import random
from typing import Annotated

from pydantic import BeforeValidator


_TIME_UNITS: dict[str, float] = {
    "ms": 0.001,
    "s": 1.0,
    "m": 60.0,
    "h": 3600.0,
}

_DURATION_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*(ms|s|m|h)\s*$",
    re.IGNORECASE,
)


def _parse_delay(value: str | float | int) -> float:
    """Coerce *value* to a float number of seconds."""
    if isinstance(value, (int, float)):
        return float(value)

    match = _DURATION_RE.fullmatch(value)
    if not match:
        raise ValueError(
            f"Invalid delay {value!r}. "
            "Expected a number followed by a unit, e.g. 100ms, 1s, 2m, 1.5h."
        )

    amount, unit = match.groups()
    return float(amount) * _TIME_UNITS[unit.lower()]


#: Annotated float (seconds) that accepts human-readable duration strings.
Duration = Annotated[float, BeforeValidator(_parse_delay)]


def _parse_range_delay(value: str | float | int) -> float:
    """Coerce *value* to a random float number of seconds within a range.

    Accepts either a plain number/duration (delegated to ``_parse_delay``) or a
    range expression such as ``200ms-2s``, ``0.5s-1.5s``, or ``1m-2m``.
    """
    if isinstance(value, (int, float)):
        return float(value)

    # Split on the *last* hyphen that is preceded by a unit character so that
    # negative numbers (not really valid here, but defensive) don't confuse us.
    range_match = re.match(
        r"^\s*"
        r"(\d+(?:\.\d+)?\s*(?:ms|s|m|h))"  # lower bound
        r"\s*-\s*"                            # separator
        r"(\d+(?:\.\d+)?\s*(?:ms|s|m|h))"  # upper bound
        r"\s*$",
        value,
        re.IGNORECASE,
    )

    if not range_match:
        # Fall back to a plain duration (e.g. "1s" passed to a RangeDuration field)
        return _parse_delay(value)

    low = _parse_delay(range_match.group(1).strip())
    high = _parse_delay(range_match.group(2).strip())

    if low > high:
        low, high = high, low

    return random.uniform(low, high)


def parse_range_delay(value: str) -> float:
    """Public wrapper — call this each iteration to get a fresh random value."""
    return _parse_range_delay(value)
