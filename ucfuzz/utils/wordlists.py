"""
Wordlist utilities.
"""

from __future__ import annotations

from pathlib import Path

from ucfuzz.exceptions import WordlistError


def get_wordlist_rows_cnt(path: Path) -> int:
    """Return the number of non-empty lines in *path*.

    Raises
    ------
    WordlistError
        If the file cannot be read.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            return sum(1 for line in fh if line.strip())
    except OSError as exc:
        raise WordlistError(f"Cannot read wordlist {path}: {exc}") from exc
