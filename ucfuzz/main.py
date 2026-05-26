"""
UCFuzz — browser-based web fuzzer.

Entry point and CLI definition.  Wires together:
  - argument parsing  (Typer)
  - schema validation (Pydantic via FuzzerOptions)
  - browser session   (BrowserEngine)
  - fuzzing loop      (Fuzzer)
  - progress display  (Rich)
  - output            (OutputWriter)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from ucfuzz.core.engine import BrowserEngine
from ucfuzz.core.fuzzer import Fuzzer
from ucfuzz.exceptions import UCFuzzError
from ucfuzz.schemas.fuzzer import FuzzerOptions, ScanResult

from ucfuzz.utils.logger import log, setup_logger
from ucfuzz.utils.output import OutputWriter
from ucfuzz.utils.wordlists import get_wordlist_rows_cnt
from ucfuzz.utils import ui

app = typer.Typer(
    help="UCFuzz — browser-based web fuzzer.",
    add_completion=False,
    rich_markup_mode="rich",
)


def _should_skip(
    result: ScanResult,
    *,
    exclude_status: Optional[list[int]],
    exclude_length: Optional[list[int]],
) -> bool:
    """Return ``True`` when *result* should be suppressed from output."""
    if result.failed:
        return True
    if exclude_status and result.status_code in exclude_status:
        return True
    if exclude_length and result.content_length in exclude_length:
        return True
    return False


def _parse_headers(raw: Optional[list[str]]) -> dict[str, str]:
    result = {}
    for item in (raw or []):
        if ":" not in item:
            raise typer.BadParameter(
                f"Invalid header {item!r}, expected 'Name: Value'")
        name, _, value = item.partition(":")
        result[name.strip()] = value.strip()
    return result


def _parse_cookies(raw: Optional[list[str]]) -> dict[str, str]:
    result = {}
    for item in (raw or []):
        if "=" not in item:
            raise typer.BadParameter(
                f"Invalid cookie {item!r}, expected 'name=value'")
        name, _, value = item.partition("=")
        result[name.strip()] = value.strip()
    return result


@app.command()
def main(
    url: str = typer.Option(
        ..., "-u", "--url",
        help="Target URL containing the [bold]FUZZ[/bold] placeholder.",
    ),
    wordlist: Path = typer.Option(
        ..., "-w", "--wordlist",
        help="Path to a plain-text wordlist (one entry per line).",
    ),
    output: Optional[Path] = typer.Option(
        None, "-o", "--output",
        help="Save results as newline-delimited JSON to this file.",
    ),
    delay: str = typer.Option(
        "5ms", "--delay",
        help="Pause between requests, e.g. [cyan]100ms[/cyan], [cyan]1s[/cyan], [cyan]2m[/cyan].",
    ),
    range_delay: Optional[str] = typer.Option(
        None, "--range-delay",
        help="Delay range between requests, e.g. '200ms-2s', '0.5s-1.5s', '1m-2m'. "
        "A random value is picked within the range on each request. "
        "Accepts units: ms, s, m, h. Overrides --delay when set."
    ),
    timeout: float = typer.Option(
        10.0, "--timeout",
        help="Seconds to wait for a response before raising a timeout.",
    ),
    exclude_length: Optional[list[int]] = typer.Option(
        None, "--exclude-length",
        help="Hide results whose content-length equals this value (repeatable).",
    ),
    exclude_status: Optional[list[int]] = typer.Option(
        [404], "--exclude-status",
        help="Hide results with this HTTP status code (repeatable).",
    ),
    headless: bool = typer.Option(
        False, "--headless",
        help="Run Chrome in headless mode (not recommended for Turnstile / JS challenges).",
    ),
    ext: Optional[str] = typer.Option(
        None, "--extension",
        help="Append this extension to every wordlist entry, e.g. [cyan]php[/cyan].",
    ),
    start: int = typer.Option(
        0,
        "--start",
        help="Index of word in wordlist to start fuzz from"
    ),
    captcha_flag: Optional[str] = typer.Option(
        None,
        "--captcha-flag",
        help="String which helps to indicate the WAF CAPTCHA page"
    ),
    headers: Optional[list[str]] = typer.Option(
        None, "--header", "-H",
        help="Extra header in 'Name: Value' format (repeatable).",
    ),
    cookies: Optional[list[str]] = typer.Option(
        None, "--cookie", "-b",
        help="Cookie in 'name=value' format (repeatable).",
    ),
) -> None:
    # -- Validate options via Pydantic ----------------------------------------
    try:
        opts = FuzzerOptions.model_validate(
            dict(url=url,
                 wordlist=wordlist,
                 delay=delay,
                 range_delay=range_delay,
                 extension=ext,
                 start_index=start,
                 headers=_parse_headers(
                     headers),
                 cookies=_parse_cookies(cookies),)
        )
    except Exception as exc:
        raise typer.BadParameter(str(exc)) from exc

    total_rows = get_wordlist_rows_cnt(opts.wordlist)
    if start >= total_rows:
        raise typer.BadParameter(
            "start parameter cannot be higher than wordlist length")

    console = Console(force_terminal=True)

    console.print(ui.build_banner(
        opts,
        delay_str=delay,
        timeout=timeout,
        headless=headless,
        exclude_length=exclude_length,
        exclude_status=exclude_status,
        output=output,
    ))

    # -- Browser stage --------------------------------------------------------
    with BrowserEngine(response_timeout=timeout,
                       headless=headless,
                       captcha_flag=captcha_flag,
                       extra_headers=opts.headers,
                       extra_cookies=opts.cookies) as browser:
        browser.start(opts.url)
        console.print(ui.browser_stage_panel())
        input("  → ")

        fuzzer = Fuzzer(opts)
        fuzzer.set_engine(browser)

        # -- Output + progress ------------------------------------------------
        with OutputWriter(output) as writer:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                setup_logger(progress.console)
                task = progress.add_task(
                    "[cyan]Fuzzing…", total=total_rows, completed=start)

                try:
                    for result in fuzzer.run():
                        progress.advance(task)

                        if _should_skip(
                            result,
                            exclude_status=exclude_status,
                            exclude_length=exclude_length,
                        ):
                            continue

                        log.bind(result=result).info("")
                        writer.write(result)
                except UCFuzzError as exc:
                    log.error(f"Scan error: {exc}")
                    raise typer.Exit(code=1) from exc
                except KeyboardInterrupt:
                    log.warning("Interrupted by user.")

                finally:
                    log.info("Scan finished.")


if __name__ == "__main__":
    app()
