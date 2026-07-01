"""
reviewforge/mdstream.py
-----------------------
Streaming Markdown renderer for ReviewForge.

As the LLM emits text chunks, this module accumulates them and re-renders
the growing markdown document in-place using Rich's `Live` display context.
The result is a smooth, flicker-free streaming output in the terminal.

Usage example:
    stream = MarkdownStream()
    for chunk in llm.stream(...):
        stream.update(chunk)
    stream.close()
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.text import Text


# ---------------------------------------------------------------------------
# Module-level default console (stderr=False → writes to stdout)
# ---------------------------------------------------------------------------
_console = Console()


class MarkdownStream:
    """
    Accumulates text chunks from an LLM stream and renders them as Rich
    Markdown in the terminal using a `Live` context for smooth updates.

    Parameters
    ----------
    mdargs : dict | None
        Extra keyword arguments forwarded verbatim to ``rich.markdown.Markdown``
        on every render call (e.g. ``{"code_theme": "monokai"}``).
    live : rich.live.Live | None
        An already-running ``Live`` instance to reuse.  When *None* (default)
        a new ``Live`` object is created internally and owned by this instance.
    """

    def __init__(
        self,
        mdargs: dict[str, Any] | None = None,
        live: Live | None = None,
    ) -> None:
        # Accumulated markdown text across all received chunks
        self._buffer: str = ""

        # Extra kwargs for rich.markdown.Markdown (e.g. code_theme, style)
        self._mdargs: dict[str, Any] = mdargs or {}

        # Track whether we own the Live context (so we know to stop it)
        self._owns_live: bool = live is None

        if live is not None:
            self._live = live
        else:
            # Create a Live context that re-renders on every update.
            # `refresh_per_second` is capped to avoid saturating the terminal.
            self._live = Live(
                Text(""),           # placeholder until first chunk arrives
                console=_console,
                refresh_per_second=12,
                vertical_overflow="visible",
            )
            self._live.start(refresh=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update(self, text: str, final: bool = False) -> None:
        """
        Append *text* to the internal buffer and re-render the markdown.

        Parameters
        ----------
        text : str
            The next chunk of text received from the LLM stream.
        final : bool
            When ``True``, this is the last chunk.  The render will include a
            trailing newline and the ``Live`` context will be stopped (if this
            instance owns it).
        """
        self._buffer += text
        self._render(final=final)

        if final:
            self._stop_live()

    def close(self) -> None:
        """
        Perform a final render (with trailing newline) and stop the ``Live``
        context.  Safe to call multiple times.
        """
        self._render(final=True)
        self._stop_live()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _render(self, final: bool = False) -> None:
        """Build a ``rich.markdown.Markdown`` object from the current buffer
        and push it into the ``Live`` display."""
        content = self._buffer

        # On the very last render we append a newline so the next terminal
        # prompt appears on a fresh line.
        if final and content and not content.endswith("\n"):
            content += "\n"

        if not content:
            # Nothing to render yet - show an empty placeholder so the Live
            # panel doesn't shift layout.
            self._live.update(Text(""))
            return

        try:
            md = Markdown(content, **self._mdargs)
            self._live.update(md)
        except Exception:
            # Graceful degradation: fall back to plain text if Markdown
            # parsing fails (e.g. malformed fence blocks mid-stream).
            self._live.update(Text(content))

    def _stop_live(self) -> None:
        """Stop the ``Live`` context if this instance owns it."""
        if self._owns_live and self._live.is_started:
            # refresh=True forces one final paint before stopping
            self._live.stop()

    # ------------------------------------------------------------------
    # Context-manager support (optional convenience)
    # ------------------------------------------------------------------

    def __enter__(self) -> "MarkdownStream":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
