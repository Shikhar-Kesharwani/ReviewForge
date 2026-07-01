"""
reviewforge/run_cmd.py

Shell command runner for ReviewForge.

Functions
---------
run_cmd(cmd, verbose, error_print, cwd)
    Run a shell command and return (return_code, combined_output).

run_cmd_with_status(cmd, status_prefix, verbose, error_print, cwd)
    Run a shell command while displaying a spinner status message.
"""

from __future__ import annotations

import subprocess
import sys
import threading
from typing import Callable, Optional

from reviewforge.waiting import Spinner


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_windows() -> bool:
    """Return True when running on Microsoft Windows."""
    return sys.platform.startswith("win")


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_cmd(
    cmd: list[str] | str,
    verbose: bool = False,
    error_print: Optional[Callable[[str], None]] = None,
    cwd: Optional[str] = None,
) -> tuple[int, str]:
    """
    Run a shell command and return its exit code and combined output.

    Both stdout and stderr are merged into a single output string.  When
    *verbose* is True, output is streamed to the terminal in real time as
    well as captured.

    Parameters
    ----------
    cmd:
        The command to run.  May be a list of strings (preferred) or a
        plain string.  On Windows the command is always passed through the
        system shell (``shell=True``).
    verbose:
        When True, lines are printed to stdout as they arrive.
    error_print:
        Optional callable that receives the full output string if the
        command exits with a non-zero return code.  Defaults to printing
        to stderr.
    cwd:
        Working directory for the subprocess.  Defaults to the current
        working directory.

    Returns
    -------
    tuple[int, str]
        ``(return_code, combined_output)``

    Examples
    --------
    >>> rc, out = run_cmd(['git', 'status'])
    >>> rc
    0
    """
    use_shell = _is_windows()

    # On Windows, if cmd is a list we join it so the shell receives a single
    # string — this mirrors how cmd.exe tokenises arguments.
    if use_shell and isinstance(cmd, list):
        import shlex
        cmd_arg: list[str] | str = subprocess.list2cmdline(cmd)
    else:
        cmd_arg = cmd

    proc = subprocess.Popen(
        cmd_arg,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,   # merge stderr into stdout
        shell=use_shell,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    output_lines: list[str] = []

    # Read line-by-line so we can stream in real time
    assert proc.stdout is not None  # guaranteed by PIPE
    for line in proc.stdout:
        output_lines.append(line)
        if verbose:
            print(line, end="", flush=True)

    proc.wait()
    combined = "".join(output_lines)

    if proc.returncode != 0:
        if error_print is not None:
            error_print(combined)
        elif not verbose:
            # Only print to stderr when we haven't already streamed the output
            print(combined, end="", file=sys.stderr)

    return proc.returncode, combined


# ---------------------------------------------------------------------------
# Status-aware runner
# ---------------------------------------------------------------------------

def run_cmd_with_status(
    cmd: list[str] | str,
    status_prefix: str = "",
    verbose: bool = False,
    error_print: Optional[Callable[[str], None]] = None,
    cwd: Optional[str] = None,
) -> tuple[int, str]:
    """
    Run a shell command while displaying a spinner status message.

    This is a thin wrapper around :func:`run_cmd` that shows a
    :class:`~reviewforge.waiting.Spinner` while the command executes.
    The spinner is suppressed when *verbose* is True (so streaming output
    is not interrupted).

    Parameters
    ----------
    cmd:
        The command to execute.
    status_prefix:
        Text shown next to the spinner, e.g. ``"Installing dependencies"``
    verbose:
        Stream output to the terminal in real time.  Spinner is hidden.
    error_print:
        Callable to receive the full output on failure.
    cwd:
        Working directory for the subprocess.

    Returns
    -------
    tuple[int, str]
        ``(return_code, combined_output)``
    """
    if verbose or not status_prefix:
        # No spinner when streaming or when no status message was requested
        return run_cmd(cmd, verbose=verbose, error_print=error_print, cwd=cwd)

    result: list[tuple[int, str]] = []
    exception_holder: list[BaseException] = []

    def _worker() -> None:
        try:
            rc, out = run_cmd(
                cmd,
                verbose=False,
                error_print=error_print,
                cwd=cwd,
            )
            result.append((rc, out))
        except BaseException as exc:  # noqa: BLE001
            exception_holder.append(exc)

    thread = threading.Thread(target=_worker, daemon=True)

    with Spinner(status_prefix):
        thread.start()
        thread.join()

    if exception_holder:
        raise exception_holder[0]

    return result[0]
