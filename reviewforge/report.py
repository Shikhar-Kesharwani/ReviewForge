"""
reviewforge/report.py

Bug reporter for ReviewForge.

When an unhandled exception occurs, installs a custom sys.excepthook that:
  - Pretty-prints the traceback using Rich
  - Offers the user an option to open a GitHub issue pre-filled with
    version information and the full traceback
"""

import os
import platform
import sys
import traceback
import webbrowser
from urllib.parse import urlencode

from rich.console import Console
from rich.traceback import Traceback

# ---------------------------------------------------------------------------
# GitHub Issues URL — update to the real repo before publishing
# ---------------------------------------------------------------------------
GITHUB_ISSUES_URL = "https://github.com/Shikhar/reviewforge/issues/new"

# Rich console used exclusively by the bug reporter
_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------

def get_version_info() -> str:
    """
    Return a formatted multi-line string containing:
      - Python version and implementation
      - Operating system / platform
      - ReviewForge package version

    This string is embedded verbatim into the body of auto-generated GitHub
    issue reports so that maintainers can reproduce the environment quickly.
    """
    try:
        from reviewforge import __version__ as rf_version
    except ImportError:
        rf_version = "unknown"

    py_version = sys.version.replace("\n", " ")
    os_info = platform.platform()

    lines = [
        "### Environment",
        f"- **ReviewForge version**: `{rf_version}`",
        f"- **Python**: `{py_version}`",
        f"- **OS**: `{os_info}`",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# GitHub issue opener
# ---------------------------------------------------------------------------

def open_issue(title: str, body: str) -> None:
    """
    Open the browser to the GitHub Issues new-issue form with *title* and
    *body* pre-filled via URL query parameters.

    Parameters
    ----------
    title : str
        The issue title (usually the exception type and message).
    body  : str
        The issue body (usually version info + formatted traceback).
    """
    params = urlencode({"title": title, "body": body})
    url = f"{GITHUB_ISSUES_URL}?{params}"
    webbrowser.open(url)


# ---------------------------------------------------------------------------
# Exception hook
# ---------------------------------------------------------------------------

def report_uncaught_exceptions(io, repo=None) -> None:
    """
    Install a custom ``sys.excepthook`` for the current process.

    When an unhandled exception propagates to the top of the call stack the
    hook will:

    1. Pretty-print the full traceback using Rich (colourised, with source
       context where possible).
    2. Display a brief apology message through *io*.
    3. Ask the user whether they want to open a GitHub issue pre-filled with
       the traceback and environment metadata.

    Parameters
    ----------
    io   : reviewforge IO object
        Must expose ``tool_error(msg)`` and ``confirm(question) -> bool``
        methods.
    repo : optional
        Reserved for future use (e.g. attaching the git remote URL to the
        report).  Currently unused.
    """

    def _hook(exc_type, exc_value, exc_tb):
        # ------------------------------------------------------------------ #
        # 1. Print a Rich traceback to stderr
        # ------------------------------------------------------------------ #
        _console.print()
        _console.print(
            "[bold red]ReviewForge encountered an unexpected error.[/bold red]"
        )
        _console.print(
            Traceback.from_exception(
                exc_type,
                exc_value,
                exc_tb,
                show_locals=False,
                suppress=[],
            )
        )

        # ------------------------------------------------------------------ #
        # 2. Notify the user via the IO abstraction
        # ------------------------------------------------------------------ #
        try:
            io.tool_error(
                "An unexpected error occurred. "
                "You may want to report this as a bug."
            )
        except Exception:
            # If io is broken we still want the rest of the handler to run
            pass

        # ------------------------------------------------------------------ #
        # 3. Offer to open a GitHub issue
        # ------------------------------------------------------------------ #
        try:
            should_report = io.confirm(
                "Would you like to open a GitHub issue with this error report?"
            )
        except Exception:
            should_report = False

        if should_report:
            # Build a concise issue title from the exception
            exc_name = exc_type.__name__ if exc_type else "UnknownError"
            exc_msg = str(exc_value)[:120] if exc_value else ""
            issue_title = f"Unhandled {exc_name}: {exc_msg}"

            # Build the issue body
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
            tb_text = "".join(tb_lines)

            version_section = get_version_info()
            issue_body = (
                f"{version_section}\n\n"
                "### Traceback\n\n"
                "```\n"
                f"{tb_text}"
                "```\n\n"
                "### Steps to reproduce\n\n"
                "_Please describe what you were doing when this happened._\n"
            )

            open_issue(issue_title, issue_body)

    # Replace the default hook
    sys.excepthook = _hook
