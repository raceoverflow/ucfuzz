""" UI helpers """

from rich.panel import Panel
from rich.text import Text

from typing import Optional
from pathlib import Path

from ucfuzz.config import VERSION
from ucfuzz.schemas.fuzzer import FuzzerOptions

_BANNER_WIDTH = 60


def build_banner(
    opts: FuzzerOptions,
    *,
    delay_str: str,
    timeout: float,
    headless: bool,
    exclude_length: Optional[list[int]],
    exclude_status: Optional[list[int]],
    output: Optional[Path],
) -> Panel:
    """Return a Rich Panel summarising the scan configuration."""
    rows = [
        ("URL",             opts.url),
        ("Wordlist",        str(opts.wordlist)),
        ("Output",          str(output) if output else "—"),
        ("Delay",           delay_str),
        ("Timeout",         f"{timeout}s"),
        ("Excluded status", ", ".join(str(s)
         for s in exclude_status) if exclude_status else "—"),
        ("Excluded length", ", ".join(str(l)
         for l in exclude_length) if exclude_length else "—"),
        ("Extension",       opts.extension or "—"),
        ("Headless",        str(headless)),
    ]

    body = Text()
    for label, value in rows:
        body.append(f"  {label:<20}", style="bold cyan")
        body.append(f"{value}\n")

    return Panel(
        body,
        title=f"[bold white]UCFuzz v{VERSION}[/bold white]  [dim]by @raceoverflow[/dim]",
        border_style="cyan",
        width=_BANNER_WIDTH,
    )


def browser_stage_panel() -> Panel:
    lines = (
        "[yellow]1.[/yellow] A browser window has been opened.\n"
        "[yellow]2.[/yellow] Log in or solve any CAPTCHA if required.\n"
        "[yellow]3.[/yellow] Press [bold]ENTER[/bold] to start fuzzing.\n"
        "           [dim](do not close the browser window)[/dim]"
    )
    return Panel(lines, title="[bold cyan]Browser Initialisation[/bold cyan]", border_style="cyan")
