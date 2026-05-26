"""
Core fuzzing loop.

:class:`Fuzzer` reads the wordlist, builds target URLs, delegates navigation
to :class:`~core.engine.BrowserEngine`, and yields :class:`~schemas.fuzzer.ScanResult`
objects for the caller to filter and display.

Separation of concerns
-----------------------
* URL construction → :meth:`FuzzerOptions.build_url` (schema layer)
* HTTP interaction  → :class:`~core.engine.BrowserEngine` (engine layer)
* Filtering/output  → ``main.py`` (CLI layer)

This means :class:`Fuzzer` itself is trivially unit-testable by injecting a
stub engine.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Optional, Protocol, runtime_checkable

from ucfuzz.schemas.types import parse_range_delay
from ucfuzz.exceptions import BrowserNotReadyError, NavigationTimeoutError, NetworkUnreachableError, CaptchaNotSolvedError
from ucfuzz.schemas.fuzzer import FuzzerOptions, ScanResult
from ucfuzz.utils.logger import log

BLACKLIST = [
    "logout",
    "log-out",
    "signout",
    "sign-out",
    "exit",
    "quit",
    "endsession",
    "revoke",
]


def word_in_blacklist(word: str) -> bool:
    for blacklist_word in BLACKLIST:
        if blacklist_word in word:
            return True
    return False


# ---------------------------------------------------------------------------
# Engine protocol — lets us inject a stub in tests without importing Selenium
# ---------------------------------------------------------------------------

@runtime_checkable
class NavigationEngine(Protocol):
    """Minimal interface that :class:`Fuzzer` requires from an engine."""

    def navigate(self, url: str) -> ScanResult:
        """Fetch *url* and return a result."""
        ...


# ---------------------------------------------------------------------------
# Fuzzer
# ---------------------------------------------------------------------------s

class Fuzzer:
    """Iterate over a wordlist and yield one :class:`ScanResult` per word.

    Parameters
    ----------
    options:
        Validated scan configuration.

    Examples
    --------
    ::

        fuzzer = Fuzzer(options)
        fuzzer.set_engine(browser_engine)
        for result in fuzzer.run():
            print(result)
    """

    def __init__(self, options: FuzzerOptions) -> None:
        self._options = options
        self._engine: Optional[NavigationEngine] = None

    def set_engine(self, engine: NavigationEngine) -> None:
        """Attach a navigation engine (typically a :class:`~core.engine.BrowserEngine`).

        Must be called before :meth:`run`.
        """
        if not isinstance(engine, NavigationEngine):
            raise TypeError(
                f"engine must implement NavigationEngine, got {type(engine).__name__}"
            )
        self._engine = engine

    def run(self) -> Iterator[ScanResult]:
        """Yield one :class:`ScanResult` per wordlist entry.

        Raises
        ------
        BrowserNotReadyError
            If :meth:`set_engine` has not been called.
        WordlistError
            If the wordlist file cannot be read.
        """
        if self._engine is None:
            raise BrowserNotReadyError(
                "Call set_engine() before run()."
            )

        opts = self._options

        try:
            wordlist_file = opts.wordlist.open(encoding="utf-8")
        except OSError as exc:
            from exceptions import WordlistError
            raise WordlistError(f"Cannot read {opts.wordlist}: {exc}") from exc

        with wordlist_file:
            word_index = 0
            for raw_word in wordlist_file:
                if word_index < opts.start_index:
                    word_index += 1
                    continue
                word = raw_word.strip()

                if word_in_blacklist(word):
                    continue

                if not word:
                    continue  # skip blank lines

                url = opts.build_url(word)
                try:
                    result = self._engine.navigate(url)
                except CaptchaNotSolvedError as ex:
                    log.error(ex)
                    log.warning(
                        "Press ENTER when you solved CAPTCHA manually...")
                    input("  → ")
                    continue
                except NavigationTimeoutError as ex:
                    log.error(ex)
                    continue
                except NetworkUnreachableError as ex:
                    log.error(ex)
                    log.warning(
                        "Press ENTER when network is reachable again...")
                    input("  → ")
                    continue
                yield result

                range_delay = opts.range_delay
                if range_delay:
                    # fresh random each time
                    random_delay = parse_range_delay(range_delay)
                    time.sleep(random_delay)
                elif opts.delay:
                    time.sleep(opts.delay)
