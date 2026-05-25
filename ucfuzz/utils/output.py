"""
Output helpers for persisting scan results to disk.

:class:`OutputWriter` is a context manager that writes one JSON line per
:class:`~schemas.fuzzer.ScanResult` to an optional output file.  When no
output path is given every ``write`` call is a no-op, so callers never need
to guard against ``None``.
"""

from __future__ import annotations

import json
from io import TextIOWrapper
from pathlib import Path
from types import TracebackType
from typing import IO, Optional, Type

from ucfuzz.schemas.fuzzer import ScanResult
from ucfuzz.utils.logger import log


class OutputWriter:
    """Write scan results as newline-delimited JSON.

    Parameters
    ----------
    path:
        Destination file.  Intermediate directories are created automatically.
        Pass ``None`` to disable file output entirely.

    Examples
    --------
    ::

        with OutputWriter(Path("results.jsonl")) as writer:
            writer.write(result)
    """

    def __init__(self, path: Optional[Path]) -> None:
        self._path = path
        self._handle: Optional[IO[str]] = None

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "OutputWriter":
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = self._path.open("a", encoding="utf-8")
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write(self, result: ScanResult) -> None:
        """Serialise *result* as a JSON line and flush to disk.

        Errors are logged and swallowed so a disk problem never aborts a scan.
        """
        if self._handle is None:
            return

        try:
            line = json.dumps(result.model_dump(), ensure_ascii=False)
            self._handle.write(line + "\n")
            self._handle.flush()
        except OSError as exc:
            log.error(f"Failed to write result to {self._path}: {exc}")

    def close(self) -> None:
        """Flush and close the underlying file handle, if open."""
        if self._handle is not None:
            try:
                self._handle.close()
            except OSError as exc:
                log.error(f"Failed to close output file {self._path}: {exc}")
            finally:
                self._handle = None
