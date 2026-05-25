"""
Custom Pydantic-compatible annotated types.

``Duration``
    A float representing seconds, parsed from human-readable strings such as
    ``100ms``, ``1s``, ``2m``, ``1.5h``.  Bare numbers are accepted as-is and
    treated as seconds.
"""

import re
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
