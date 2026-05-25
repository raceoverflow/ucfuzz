"""
Pydantic models for UCFuzz configuration and scan results.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, FilePath, HttpUrl, field_validator, model_validator

from ucfuzz.schemas.types import Duration


class FuzzerOptions(BaseModel):
    """Validated, normalised options passed to :class:`~core.fuzzer.Fuzzer`.

    Parameters
    ----------
    url:
        Target URL.  Must contain the literal string ``FUZZ`` which will be
        replaced with each wordlist entry during the scan.
    wordlist:
        Path to a plain-text wordlist (one entry per line).
    delay:
        Pause between requests expressed as a human-readable duration string
        (``100ms``, ``1s``, ``2m``) or a bare float (seconds).  Defaults to 0.
    extension:
        Optional file extension appended to every wordlist entry, *without* the
        leading dot (e.g. ``php``, ``html``).
    """

    url: str  # stored as str after validation so FUZZ replacement is safe
    wordlist: FilePath
    delay: Duration = 0.05
    extension: Optional[str] = None
    start_index: int = 0

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_validator("url", mode="before")
    @classmethod
    def _normalise_url(cls, v: object) -> str:
        """Accept both raw strings and Pydantic HttpUrl objects."""
        raw = str(v).rstrip("/")
        # Basic sanity check — let HttpUrl do the real validation first via
        # a temporary parse so we get a helpful error message.
        HttpUrl(raw)  # raises ValidationError if invalid
        return raw

    @model_validator(mode="after")
    def _require_fuzz_marker(self) -> FuzzerOptions:
        if "FUZZ" not in self.url:
            raise ValueError("url must contain the FUZZ placeholder.")
        return self

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def ext_suffix(self) -> str:
        """Return the extension with a leading dot, or an empty string."""
        return f".{self.extension}" if self.extension else ""

    def build_url(self, word: str) -> str:
        """Replace the FUZZ marker with *word* (plus any configured extension)."""
        return self.url.replace("FUZZ", word + self.ext_suffix)


class ScanResult(BaseModel):
    """The outcome of a single fuzzing request.

    Parameters
    ----------
    url:
        The fully-expanded URL that was requested.
    status_code:
        HTTP status code returned by the server, or ``0`` when the request
        failed (timeout, network error, etc.).
    content_length:
        Response body size in bytes.  Falls back to the rendered page-source
        length when the ``Content-Length`` header is absent.
    """

    url: str
    status_code: int
    content_length: int

    @property
    def failed(self) -> bool:
        """``True`` when no valid HTTP response was received."""
        return self.status_code == 0
