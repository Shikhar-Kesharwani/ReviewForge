"""
reviewforge/editor.py

External editor integration for ReviewForge.

Opens the user's preferred text editor with a temporary file, waits for the
editor process to exit, and returns whatever the user wrote — or None if the
content is unchanged / empty.
"""

import os
import platform
import subprocess
import tempfile
from typing import Optional


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_default_editor() -> str:
    """Return the editor command to use, checked in priority order.

    Checks the following sources in order:

    1. ``VISUAL`` environment variable.
    2. ``EDITOR`` environment variable.
    3. Platform default: ``notepad`` on Windows, ``nano`` on all others.

    Returns
    -------
    str
        A command string suitable for passing to :func:`subprocess.run`.
    """
    for env_var in ("VISUAL", "EDITOR"):
        value = os.environ.get(env_var, "").strip()
        if value:
            return value

    # Platform fall-back.
    if platform.system().lower() == "windows":
        return "notepad"
    return "nano"


def pipe_editor(
    initial_text: str = "",
    suffix: str = ".md",
    editor: Optional[str] = None,
) -> Optional[str]:
    """Open an external editor and return the text the user typed.

    Writes *initial_text* to a temporary file, opens it in the chosen editor,
    waits for the editor process to exit, then reads the (possibly modified)
    file content back.

    Parameters
    ----------
    initial_text:
        Text to pre-populate the temporary file with before opening the
        editor.  Useful for showing existing content or a template.
    suffix:
        File extension for the temporary file (default ``'.md'``).  Some
        editors use the extension for syntax highlighting.
    editor:
        Explicit editor command to use.  When ``None``, :func:`get_default_editor`
        is called to determine the right command.

    Returns
    -------
    str | None
        The text the user saved in the editor, stripped of leading/trailing
        whitespace.  Returns ``None`` if:

        * The content is identical to *initial_text* (no change was made).
        * The resulting content is empty or contains only whitespace.

    Raises
    ------
    OSError
        If the temporary file cannot be created or read.
    subprocess.CalledProcessError
        If the editor process exits with a non-zero status code.
    """
    chosen_editor = editor or get_default_editor()

    # Create a named temp file that the editor can open by path.
    # ``delete=False`` so the file persists after the ``with`` block; we
    # clean it up manually in the ``finally`` clause.
    tmp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            encoding="utf-8",
            delete=False,
        ) as tmp_file:
            tmp_path = tmp_file.name
            if initial_text:
                tmp_file.write(initial_text)

        # Launch the editor synchronously (block until it closes).
        # On Windows, ``notepad`` is a GUI app so subprocess.run will still
        # wait because it is called without ``shell=True``.
        subprocess.run(
            [chosen_editor, tmp_path],
            check=True,
        )

        # Read back the (possibly modified) content.
        with open(tmp_path, encoding="utf-8") as fh:
            new_content = fh.read()

    finally:
        # Always clean up the temporary file.
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass  # Best-effort cleanup; don't mask the original error.

    stripped = new_content.strip()

    # Return None for empty or unchanged content.
    if not stripped or stripped == initial_text.strip():
        return None

    return stripped
