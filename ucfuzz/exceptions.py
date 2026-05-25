"""
UCFuzz — custom exception hierarchy.

All domain-specific exceptions live here so callers can catch
narrowly without importing from unrelated modules.
"""


class UCFuzzError(Exception):
    """Base class for all UCFuzz errors."""


class BrowserNotReadyError(UCFuzzError):
    """Raised when a Fuzzer method is called before a browser is attached."""


class NavigationTimeoutError(UCFuzzError):
    """Raised when the browser does not receive a response within the timeout."""

    def __init__(self, url: str, timeout: float) -> None:
        self.url = url
        self.timeout = timeout
        super().__init__(f"No response for {url!r} within {timeout}s")


class WordlistError(UCFuzzError):
    """Raised for problems reading or parsing the wordlist."""
