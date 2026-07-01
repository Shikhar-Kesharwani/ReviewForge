"""
reviewforge/copypaste.py

Clipboard watcher and helpers for ReviewForge's copy-paste web-UI integration.

When users work with the ReviewForge web interface they can copy edit blocks
from the browser and paste them directly into the terminal session.  The
:class:`ClipboardWatcher` monitors the system clipboard in a background
thread and fires a callback whenever it detects a ReviewForge-formatted
edit block.
"""

import threading
import time
from typing import Callable, Optional

try:
    import pyperclip  # type: ignore[import-untyped]
    _PYPERCLIP_AVAILABLE = True
except ImportError:
    _PYPERCLIP_AVAILABLE = False


# ---------------------------------------------------------------------------
# Detection helper
# ---------------------------------------------------------------------------

# Keywords that indicate the clipboard content looks like a ReviewForge edit
# block (search/replace format used by the diff-editing subsystem).
_EDIT_BLOCK_MARKERS = ("<<<<<<< SEARCH", ">>>>>>> REPLACE", "SEARCH", "REPLACE")


def _looks_like_edit_block(text: str) -> bool:
    """Return True if *text* resembles a ReviewForge edit block."""
    return any(marker in text for marker in _EDIT_BLOCK_MARKERS)


# ---------------------------------------------------------------------------
# ClipboardWatcher
# ---------------------------------------------------------------------------


class ClipboardWatcher:
    """Background-thread clipboard monitor.

    Polls the system clipboard every :attr:`poll_interval` seconds.  When the
    clipboard content changes *and* looks like a ReviewForge edit block, the
    provided *callback* is invoked with the clipboard text as its only
    argument.

    Parameters
    ----------
    callback:
        Callable invoked with ``(text: str)`` whenever a qualifying clipboard
        change is detected.
    poll_interval:
        Seconds between polls (default ``0.5``).

    Usage
    -----
    As a context manager (preferred)::

        def handle(text):
            print("Got edit block:", text[:80])

        with ClipboardWatcher(callback=handle):
            time.sleep(60)   # watch for one minute

    Or manually::

        watcher = ClipboardWatcher(callback=handle)
        watcher.start()
        # ... do other work ...
        watcher.stop()
    """

    def __init__(
        self,
        callback: Callable[[str], None],
        poll_interval: float = 0.5,
    ) -> None:
        self._callback = callback
        self.poll_interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # Seed with the current clipboard content so we don't fire
        # immediately for pre-existing text.
        self._last_text: str = paste_from_clipboard() or ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread is not None and self._thread.is_alive():
            return  # Already running.
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="reviewforge-clipboard-watcher",
            daemon=True,  # Dies automatically when the main process exits.
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the background thread to stop and wait for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=self.poll_interval * 4)
            self._thread = None

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "ClipboardWatcher":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main loop executed in the background thread."""
        while not self._stop_event.is_set():
            try:
                current = paste_from_clipboard()
                if current is not None and current != self._last_text:
                    self._last_text = current
                    if _looks_like_edit_block(current):
                        try:
                            self._callback(current)
                        except Exception:  # noqa: BLE001
                            # Never let a callback error crash the watcher.
                            pass
            except Exception:  # noqa: BLE001
                # Clipboard access can fail transiently (e.g. another process
                # holds the clipboard lock).  We simply skip this tick.
                pass

            # Honour the stop event mid-sleep for faster shutdown.
            self._stop_event.wait(timeout=self.poll_interval)


# ---------------------------------------------------------------------------
# Clipboard helpers
# ---------------------------------------------------------------------------


def copy_to_clipboard(text: str) -> bool:
    """Copy *text* to the system clipboard.

    Parameters
    ----------
    text:
        The string to place on the clipboard.

    Returns
    -------
    bool
        ``True`` on success, ``False`` if ``pyperclip`` is not available or
        an error occurred.
    """
    if not _PYPERCLIP_AVAILABLE:
        return False
    try:
        pyperclip.copy(text)
        return True
    except Exception:  # noqa: BLE001
        return False


def paste_from_clipboard() -> Optional[str]:
    """Read the current clipboard contents.

    Returns
    -------
    str | None
        The clipboard text, or ``None`` if ``pyperclip`` is unavailable or
        the read fails.
    """
    if not _PYPERCLIP_AVAILABLE:
        return None
    try:
        return pyperclip.paste()
    except Exception:  # noqa: BLE001
        return None
