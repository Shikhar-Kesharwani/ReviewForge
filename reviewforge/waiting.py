"""
reviewforge/waiting.py

Terminal spinner for ReviewForge.

Displays a Braille-dot rotating animation next to a status message while
a long-running operation executes in the background.  Designed to work on
Windows terminals that may not support ANSI escape sequences — it uses only
a plain carriage-return (``\\r``) to overwrite the current line.

Classes
-------
Spinner
    Context-manager spinner that runs in a daemon thread.

Functions
---------
spinner(msg)
    Convenience context-manager wrapper around :class:`Spinner`.

Usage
-----
::

    from reviewforge.waiting import spinner

    with spinner("Analysing code"):
        do_slow_thing()

    # or more explicitly:
    from reviewforge.waiting import Spinner

    with Spinner("Fetching model response"):
        response = call_llm()
"""

from __future__ import annotations

import sys
import threading
import time
from contextlib import contextmanager
from typing import Generator, Optional


# ---------------------------------------------------------------------------
# Spinner frames
# ---------------------------------------------------------------------------

#: Braille-dot spinner frames (one full rotation)
_FRAMES: tuple[str, ...] = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")

#: Fallback ASCII frames for environments that cannot render Braille
_ASCII_FRAMES: tuple[str, ...] = ("|", "/", "-", "\\")

#: How long each frame is displayed (seconds)
_FRAME_INTERVAL: float = 0.1


# ---------------------------------------------------------------------------
# Spinner class
# ---------------------------------------------------------------------------

class Spinner:
    """
    Thread-backed terminal spinner used as a context manager.

    The spinner prints rotating animation frames followed by *msg* to
    stderr.  Each update overwrites the current line using ``\\r`` so no
    ANSI escape codes are required (Windows-safe).

    When the context exits (whether normally or via an exception) the
    spinner line is cleared before the caller's output continues.

    Parameters
    ----------
    msg:
        Status text displayed next to the spinner, e.g.
        ``"Loading model…"``.
    interval:
        Seconds between frame updates.  Defaults to :data:`_FRAME_INTERVAL`.
    stream:
        File-like object to write to.  Defaults to ``sys.stderr``.

    Examples
    --------
    ::

        with Spinner("Installing packages"):
            run_pip_install()
    """

    def __init__(
        self,
        msg: str = "",
        interval: float = _FRAME_INTERVAL,
        stream=None,
    ) -> None:
        self.msg = msg
        self.interval = interval
        self._stream = stream or sys.stderr

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        # Choose frame set based on whether the terminal can render Braille
        self._frames = self._choose_frames()

    # ------------------------------------------------------------------ #
    # Frame selection
    # ------------------------------------------------------------------ #

    def _choose_frames(self) -> tuple[str, ...]:
        """
        Return Braille frames when the terminal encoding supports them,
        otherwise fall back to plain ASCII.
        """
        encoding = getattr(self._stream, "encoding", None) or "ascii"
        try:
            "⠋".encode(encoding)
            return _FRAMES
        except (UnicodeEncodeError, LookupError):
            return _ASCII_FRAMES

    # ------------------------------------------------------------------ #
    # Background thread target
    # ------------------------------------------------------------------ #

    def _spin(self) -> None:
        """Continuously write spinner frames until the stop event fires."""
        frame_idx = 0
        while not self._stop_event.is_set():
            frame = self._frames[frame_idx % len(self._frames)]
            # Build the display line; pad to 80 chars so previous text is
            # fully overwritten when the message is shorter than the last one.
            line = f"\r{frame} {self.msg}"
            try:
                self._stream.write(line)
                self._stream.flush()
            except Exception:  # noqa: BLE001
                # If the stream fails (e.g. closed pipe) just stop gracefully
                break

            frame_idx += 1
            # Use the event's wait() rather than time.sleep() so we can
            # stop promptly when the event fires.
            self._stop_event.wait(timeout=self.interval)

    # ------------------------------------------------------------------ #
    # Context manager protocol
    # ------------------------------------------------------------------ #

    def __enter__(self) -> "Spinner":
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        # Signal the spinner thread to stop and wait for it to finish
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

        # Clear the spinner line so the caller's output starts cleanly
        clear_line = "\r" + " " * (len(self.msg) + 4) + "\r"
        try:
            self._stream.write(clear_line)
            self._stream.flush()
        except Exception:  # noqa: BLE001
            pass

        # Do not suppress exceptions — return False (falsy)
        return False

    # ------------------------------------------------------------------ #
    # Additional convenience
    # ------------------------------------------------------------------ #

    def update(self, msg: str) -> None:
        """
        Update the status message while the spinner is running.

        Parameters
        ----------
        msg:
            New status text.
        """
        self.msg = msg


# ---------------------------------------------------------------------------
# Convenience context-manager function
# ---------------------------------------------------------------------------

@contextmanager
def spinner(msg: str, interval: float = _FRAME_INTERVAL) -> Generator[Spinner, None, None]:
    """
    Convenience context manager that wraps :class:`Spinner`.

    Parameters
    ----------
    msg:
        Status message to display next to the spinner.
    interval:
        Seconds between frame updates.

    Yields
    ------
    Spinner
        The running :class:`Spinner` instance (in case the caller wants to
        call :meth:`Spinner.update`).

    Examples
    --------
    ::

        with spinner("Generating review") as sp:
            result = model.complete(prompt)
            sp.update("Finalising…")
    """
    with Spinner(msg, interval=interval) as sp:
        yield sp
