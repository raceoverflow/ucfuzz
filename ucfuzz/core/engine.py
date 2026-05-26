"""
Browser automation layer built on SeleniumBase + Chrome DevTools Protocol (CDP).

Architecture
------------
``BrowserEngine``
    High-level context manager.  Owns the SeleniumBase session and exposes
    :meth:`start` (initial page + optional CAPTCHA) and :meth:`navigate`
    (per-URL fuzzing step).

``_ResponseTracker``
    Encapsulates all CDP response-tracking state.  Uses a **generation
    counter** to avoid the race where the CDP handler fires *during*
    ``cdp.open()`` — before the main thread reaches ``wait()`` — causing the
    event to be missed.

Race condition this design prevents
------------------------------------
The naive approach is: reset() → cdp.open() → wait().
The problem: cdp.open() can block while the browser is already receiving the
response, so the CDP handler fires and sets the event *before* wait() is
called.  When wait() finally runs the event is already set and returns
immediately — but reset() already cleared it, so it appears as a timeout.

Fix: arm() records the current generation *before* open() is called.  The
handler increments the generation when a record arrives for the active
generation.  wait_for_generation() blocks until the counter advances past the
snapshot taken before open(), so it cannot miss an early response.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

import mycdp

from ucfuzz.exceptions import NavigationTimeoutError, NetworkUnreachableError
from ucfuzz.schemas.fuzzer import ScanResult
from ucfuzz.utils.logger import log


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

@dataclass
class _ResponseRecord:
    """A single HTTP response observed via CDP."""
    url: str
    status_code: int
    content_length: int


class _ResponseTracker:
    """Thread-safe, race-free accumulator for CDP ``ResponseReceived`` events.

    Usage pattern (main thread)::

        token = tracker.arm()          # snapshot generation BEFORE open()
        sb.cdp.open(url)               # response may arrive here …
        ok = tracker.wait(token, 10)   # … but we won't miss it
        records = tracker.records_for(token)
    """

    def __init__(self) -> None:
        # Single lock used everywhere — _condition IS the lock.
        # Never acquire self._condition.acquire() / self._lock separately;
        # always use `with self._condition` so notify_all() is never missed.
        self._condition = threading.Condition()
        self._generation: int = 0
        self._records: list[tuple[int, _ResponseRecord]] = []  # (gen, record)

    # ------------------------------------------------------------------
    # CDP handler — called from a background thread
    # ------------------------------------------------------------------

    def handle(self, event: mycdp.network.ResponseReceived) -> None:
        """Ingest one CDP response event and wake any waiting main thread."""
        try:
            resp = event.response
            headers = resp.headers or {}
            content_length = int(headers.get("content-length", 0) or 0)
            record = _ResponseRecord(
                url=resp.url,
                status_code=resp.status,
                content_length=content_length,
            )
            with self._condition:
                self._records.append((self._generation, record))
                self._condition.notify_all()
        except Exception as exc:  # noqa: BLE001
            log.error(f"CDP response handler error: {exc}")

    # ------------------------------------------------------------------
    # Main-thread API
    # ------------------------------------------------------------------

    def arm(self) -> int:
        """Advance the generation counter and return its new value.

        Call this *before* ``cdp.open()`` so the handler tags any response
        that arrives during open() with the correct generation.
        """
        with self._condition:
            cutoff = self._generation
            self._generation += 1
            # Keep only the previous generation's records in case best_match()
            # is called just after arm() — drop everything older.
            self._records = [(generation, record) for generation,
                             record in self._records if generation >= cutoff]
            return self._generation

    def wait(self, generation: int, timeout: float) -> bool:
        """Block until a record tagged *generation* exists, or *timeout* expires.

        Uses ``Condition.wait_for`` so the predicate is checked *before*
        blocking — a notify that fired during ``cdp.open()`` (before this
        method is called) is never missed because the record is already in
        ``self._records`` and the predicate returns True immediately.

        Returns ``True`` if at least one matching record arrived.
        """
        with self._condition:
            return self._condition.wait_for(
                lambda: self._has_record(generation),
                timeout=timeout,
            )

    def records_for(self, generation: int) -> list[_ResponseRecord]:
        """Return a snapshot of all records tagged with *generation*."""
        with self._condition:
            return [r for g, r in self._records if g == generation]

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    def _has_record(self, generation: int) -> bool:
        """Predicate — must be called with self._condition held."""
        return any(g == generation for g, _ in self._records)

    def best_match(
        self, records: list[_ResponseRecord], requested_url: str
    ) -> Optional[_ResponseRecord]:
        """Return the record that best matches *requested_url*.

        Priority:
        1. Exact URL match (no redirect).
        2. Prefix match on the path (redirect chain).
        3. First record (SPA URL rewrite).
        """
        base = requested_url.split("?")[0]

        for rec in records:
            if rec.url == requested_url:
                return rec

        for rec in records:
            if rec.url.startswith(base):
                return rec

        return records[0] if records else None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class BrowserEngine:
    """Manage a Chrome/Chromium session for browser-based fuzzing.

    Use as a context manager::

        with BrowserEngine(response_timeout=10, headless=False) as engine:
            engine.start("https://target.com/FUZZ")
            # … wait for user to log in …
            result = engine.navigate("https://target.com/admin")

    Parameters
    ----------
    response_timeout:
        Seconds to wait for the first CDP response event after each navigation.
    headless:
        Run Chrome without a visible window.  Turnstile / JS challenges usually
        require ``headless=False``.
    """

    def __init__(self, response_timeout: float = 10.0, headless: bool = False) -> None:
        self._timeout = response_timeout
        self._headless = headless

        self._sb: Any = None          # SeleniumBase driver
        self._sb_ctx: Any = None      # SeleniumBase context manager
        self._tracker = _ResponseTracker()

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "BrowserEngine":
        from seleniumbase import SB  # local import — optional heavy dependency

        self._sb_ctx = SB(
            uc=True,
            test=False,
            locale_code="en",
            headless=self._headless,
        )
        self._sb = self._sb_ctx.__enter__()
        self._sb.activate_cdp_mode("about:blank")
        self._sb.cdp.add_handler(
            mycdp.network.ResponseReceived,
            self._tracker.handle,
        )
        return self

    def __exit__(self, *args: object) -> None:
        self._quit()

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def start(self, url: str) -> None:
        """Open *url* and give the user a chance to complete any login / CAPTCHA.

        The method attempts an automated CAPTCHA solve via SeleniumBase; if
        that fails the user can solve it manually before pressing ENTER.
        """
        try:
            self._sb.cdp.open(url)
            time.sleep(2)
        except Exception as exc:
            log.error(f"Failed to open {url!r}: {exc}")
            raise

        try:
            self._sb.cdp.solve_captcha()
        except Exception as exc:
            log.warning(
                f"Automated CAPTCHA solve failed (you can solve it manually): {exc}")

        time.sleep(2)

    def navigate(self, url: str) -> ScanResult:
        """Navigate to *url* and return the observed HTTP response.

        Parameters
        ----------
        url:
            Fully expanded target URL (FUZZ already replaced).

        Returns
        -------
        ScanResult
            Contains the URL, status code, and content length.
            ``status_code=0`` indicates a failed request (timeout / error).

        Raises
        ------
        NavigationTimeoutError
            If no CDP response is received within ``response_timeout`` seconds.

        NetworkUnreachableError
            If received ResponseRecord url starting with 'data:image' which indicated network error
        """
        # arm() MUST be called before cdp.open() — it snapshots the generation
        # counter so that responses arriving *during* open() are not missed.
        generation = self._tracker.arm()

        try:
            self._sb.cdp.open(url)
        except Exception as exc:
            log.error(f"Navigation error for {url!r}: {exc}")
            return ScanResult(url=url, status_code=0, content_length=0)

        received = self._tracker.wait(generation, self._timeout)
        if not received:
            raise NavigationTimeoutError(url, self._timeout)

        records = self._tracker.records_for(generation)
        record = self._tracker.best_match(records, url)

        if record is None:
            log.warning(f"No response record found for {url!r}")
            return ScanResult(url=url, status_code=0, content_length=0)

        # Fall back to rendered page-source length when header is absent
        content_length = record.content_length or len(
            self._sb.cdp.get_page_source())

        if record.url.startswith("data:image"):
            raise NetworkUnreachableError

        return ScanResult(
            url=url,
            status_code=record.status_code,
            content_length=content_length,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _quit(self) -> None:
        try:
            if self._sb_ctx is not None:
                self._sb_ctx.__exit__(None, None, None)
        except Exception as exc:
            log.error(f"Error shutting down browser: {exc}")
        finally:
            self._sb = None
            self._sb_ctx = None
