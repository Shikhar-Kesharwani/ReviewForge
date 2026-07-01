"""
reviewforge/diffs.py

Diff display utilities for ReviewForge.

Provides helpers to compute unified diffs between file versions and render
them in colour on the terminal using the ``rich`` library.
"""

import difflib
from typing import Any

from rich.console import Console
from rich.text import Text


# ---------------------------------------------------------------------------
# Diff computation
# ---------------------------------------------------------------------------


def diff_content(fname: str, orig: str, updated: str) -> str:
    """Compute a unified diff between *orig* and *updated* for file *fname*.

    Parameters
    ----------
    fname:
        The logical file name shown in the diff header.
    orig:
        Original file content (before the change).
    updated:
        New file content (after the change).

    Returns
    -------
    str
        A unified-diff string.  Empty string if there are no differences.
    """
    orig_lines = orig.splitlines(keepends=True)
    updated_lines = updated.splitlines(keepends=True)

    diff_lines = list(
        difflib.unified_diff(
            orig_lines,
            updated_lines,
            fromfile=f"a/{fname}",
            tofile=f"b/{fname}",
        )
    )
    return "".join(diff_lines)


# ---------------------------------------------------------------------------
# Diff header
# ---------------------------------------------------------------------------


def get_diff_header(fname: str) -> str:
    """Return the standard unified-diff file header for *fname*.

    Parameters
    ----------
    fname:
        File path or name to embed in the header.

    Returns
    -------
    str
        A two-line header of the form ``--- a/fname\\n+++ b/fname``.
    """
    return f"--- a/{fname}\n+++ b/{fname}"


# ---------------------------------------------------------------------------
# Colourised rendering
# ---------------------------------------------------------------------------


def show_diff(diff_text: str, io: Any = None) -> None:
    """Print a colourised unified diff to the terminal.

    Lines are colour-coded following the universal convention:

    * **Red** — removed lines (starting with ``-``).
    * **Green** — added lines (starting with ``+``).
    * **Dim** — context lines and hunk headers.

    Parameters
    ----------
    diff_text:
        A unified-diff string as returned by :func:`diff_content` or
        ``difflib.unified_diff``.
    io:
        Optional I/O object.  If it exposes a ``write`` method it will be
        used for output; otherwise a fresh ``rich.console.Console`` writes
        directly to *stdout*.  Pass ``None`` to always use stdout.
    """
    # Decide where to write output.
    if io is not None and hasattr(io, "write"):
        # Wrap the plain writer in a Rich console so we get markup support.
        console = Console(highlight=False, file=io)
    else:
        console = Console(highlight=False)

    if not diff_text:
        console.print("[dim]No differences.[/dim]")
        return

    for line in diff_text.splitlines():
        styled = _style_diff_line(line)
        console.print(styled, end="\n", markup=False, highlight=False)


def _style_diff_line(line: str) -> Text:
    """Return a ``rich.text.Text`` object styled for a single diff *line*."""
    text = Text(line)

    if line.startswith("+++") or line.startswith("---"):
        # File header lines — bold and dim to distinguish from change lines.
        text.stylize("bold dim")
    elif line.startswith("+"):
        text.stylize("green")
    elif line.startswith("-"):
        text.stylize("red")
    elif line.startswith("@@"):
        # Hunk header.
        text.stylize("cyan dim")
    else:
        # Unchanged context lines.
        text.stylize("dim")

    return text
