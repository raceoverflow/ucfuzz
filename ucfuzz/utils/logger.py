from __future__ import annotations

from loguru import logger
from rich.console import Console

from ucfuzz.schemas.fuzzer import ScanResult


# ---------------------------------------------------------------------------
# Internal format helpers
# ---------------------------------------------------------------------------

def _format_result(result: ScanResult) -> str:
    """Render a scan hit as Rich markup."""

    if result.status_code >= 500:
        status_color = "red"
    elif result.status_code >= 400:
        status_color = "yellow"
    elif result.status_code >= 300:
        status_color = "blue"
    else:
        status_color = "green"

    return (
        f"[green]{result.url}[/green] "
        f"(Status: [{status_color}]{result.status_code}[/{status_color}]) "
        f"[Size: [cyan]{result.content_length}[/cyan]]"
    )


def _format_log(record: dict) -> str:
    """Render a standard log entry."""

    level = record["level"].name

    level_color = {
        "ERROR": "red",
        "WARNING": "yellow",
        "CRITICAL": "bold red",
    }.get(level, "cyan")

    return (
        f"[{level_color}]{level:<8}[/{level_color}] "
        f"{record['message']}"
    )


def _format_record(record: dict) -> str:
    """Dispatch formatter."""

    result: ScanResult | None = record["extra"].get("result")

    if result:
        return _format_result(result)

    return _format_log(record)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def setup_logger(console: Console) -> None:
    """Configure Loguru to render through Rich."""

    logger.remove()

    def sink(message):
        record = message.record
        console.print(
            _format_record(record),
            soft_wrap=True,
            markup=True,
        )

    logger.add(
        sink,
        colorize=False,
    )


log = logger
