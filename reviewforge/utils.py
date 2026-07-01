"""
reviewforge/utils.py

Shared utility functions for ReviewForge.

Functions
---------
is_image_file(fname)        -- True if fname has an image extension
get_pip_install(packages)   -- build a `pip install` subprocess command list
format_content(role, content) -- format a single chat message for display
format_messages(msgs)       -- format a list of chat messages for display
hash_text(text)             -- MD5 hex digest of a string
touch_file(fname)           -- create an empty file (and parent dirs)
safe_abs_path(path)         -- resolve to an absolute string path
show_messages(msgs, ...)    -- pretty-print messages to stderr
"""

from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path
from typing import Any, Iterable


# ---------------------------------------------------------------------------
# Image detection
# ---------------------------------------------------------------------------

#: Extensions treated as image files (lower-case, without leading dot)
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {"png", "jpg", "jpeg", "gif", "webp", "bmp"}
)


def is_image_file(fname: str | os.PathLike) -> bool:
    """
    Return True if *fname* has a recognised image file extension.

    The comparison is case-insensitive.

    Parameters
    ----------
    fname:
        File name or path to inspect.

    Examples
    --------
    >>> is_image_file("photo.PNG")
    True
    >>> is_image_file("document.pdf")
    False
    """
    suffix = Path(fname).suffix.lstrip(".").lower()
    return suffix in IMAGE_EXTENSIONS


# ---------------------------------------------------------------------------
# pip install helper
# ---------------------------------------------------------------------------

def get_pip_install(packages: Iterable[str]) -> list[str]:
    """
    Return a subprocess command list for installing *packages* with pip.

    Uses ``sys.executable`` so the correct interpreter / virtual-env is
    always targeted.

    Parameters
    ----------
    packages:
        One or more package specifiers (e.g. ``['litellm>=1.0', 'rich']``).

    Returns
    -------
    list[str]
        Command suitable for passing to :func:`subprocess.run` etc.

    Examples
    --------
    >>> get_pip_install(['litellm', 'rich'])
    ['/usr/bin/python3', '-m', 'pip', 'install', 'litellm', 'rich']
    """
    return [sys.executable, "-m", "pip", "install", *packages]


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------

def format_content(role: str, content: Any) -> str:
    """
    Format a single chat message (role + content) as a human-readable string.

    When *content* is a list (multi-part messages, e.g. image + text),
    each part is rendered on its own line.

    Parameters
    ----------
    role:
        The message role (``'user'``, ``'assistant'``, ``'system'``, …).
    content:
        The message body — either a plain string or a list of content parts.

    Returns
    -------
    str
        A formatted, multi-line string representation.
    """
    role_label = role.upper()

    if isinstance(content, list):
        # Multi-part content (e.g. vision messages)
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                part_type = part.get("type", "unknown")
                if part_type == "text":
                    parts.append(part.get("text", ""))
                elif part_type == "image_url":
                    url = part.get("image_url", {})
                    if isinstance(url, dict):
                        url = url.get("url", "<image>")
                    parts.append(f"<image: {url}>")
                else:
                    parts.append(repr(part))
            else:
                parts.append(str(part))
        body = "\n".join(parts)
    else:
        body = str(content) if content is not None else ""

    return f"[{role_label}]\n{body}"


def format_messages(msgs: list[dict]) -> str:
    """
    Format a list of chat messages for display or logging.

    Parameters
    ----------
    msgs:
        List of message dicts, each with at least ``'role'`` and
        ``'content'`` keys.

    Returns
    -------
    str
        A multi-line string with each message separated by a divider.
    """
    divider = "-" * 60
    sections: list[str] = []
    for msg in msgs:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        sections.append(format_content(role, content))
    return f"\n{divider}\n".join(sections)


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def hash_text(text: str) -> str:
    """
    Return the MD5 hex digest of *text*.

    Primarily used for cache-key generation and change detection — not for
    security purposes.

    Parameters
    ----------
    text:
        The input string to hash.

    Returns
    -------
    str
        32-character lowercase hexadecimal string.
    """
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()


# ---------------------------------------------------------------------------
# File system helpers
# ---------------------------------------------------------------------------

def touch_file(fname: str | os.PathLike) -> None:
    """
    Create *fname* as an empty file, creating parent directories as needed.

    If the file already exists its modification time is updated (standard
    ``touch`` behaviour).

    Parameters
    ----------
    fname:
        Path of the file to create / touch.
    """
    path = Path(fname)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(exist_ok=True)


def safe_abs_path(path: str | os.PathLike) -> str:
    """
    Return the absolute, resolved path as a plain string.

    Resolves ``~``, ``..``, and symlinks.  Does NOT require the path to
    exist on disk.

    Parameters
    ----------
    path:
        Input path (relative, absolute, or containing ``~``).

    Returns
    -------
    str
        Absolute, resolved path.
    """
    return str(Path(path).expanduser().resolve())


# ---------------------------------------------------------------------------
# Message display
# ---------------------------------------------------------------------------

def show_messages(
    msgs: list[dict],
    prefix: str = "",
    max_length: int | None = None,
) -> None:
    """
    Pretty-print a list of chat messages to *stderr*.

    Parameters
    ----------
    msgs:
        List of message dicts (``role`` / ``content``).
    prefix:
        Optional label printed before the message block.
    max_length:
        If given, truncate each message body to this many characters and
        append ``'…'`` to indicate truncation.
    """
    if prefix:
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"  {prefix}", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)

    for idx, msg in enumerate(msgs):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        formatted = format_content(role, content)

        if max_length is not None and len(formatted) > max_length:
            formatted = formatted[:max_length] + "…"

        print(f"\n--- message {idx + 1} ---", file=sys.stderr)
        print(formatted, file=sys.stderr)

    print("", file=sys.stderr)
