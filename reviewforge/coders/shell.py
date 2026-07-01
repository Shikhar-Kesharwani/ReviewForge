"""
reviewforge/coders/shell.py

Shell command detection in LLM responses.

When the LLM suggests running shell commands it wraps them in fenced code
blocks labelled ``bash``, ``sh``, or ``shell``.  This module extracts those
commands so ReviewForge can present them to the user for optional execution.
"""

from __future__ import annotations

import re
from typing import Iterator, List

# ---------------------------------------------------------------------------
# Regex — matches fenced code blocks with a bash/sh/shell language tag.
# Captures everything between the opening and closing fences.
# ---------------------------------------------------------------------------

_SHELL_FENCE_RE = re.compile(
    r"```[ \t]*(?:bash|sh|shell)[ \t]*\n"   # opening fence + language tag
    r"(.*?)"                                  # captured command(s) — non-greedy
    r"```",                                   # closing fence
    re.DOTALL | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# ShellCMDs — thin wrapper around a list of extracted command strings
# ---------------------------------------------------------------------------


class ShellCMDs:
    """
    A container for shell commands extracted from an LLM response.

    Supports truthiness testing (``if shell_cmds:``) and iteration
    (``for cmd in shell_cmds:``).

    Parameters
    ----------
    cmds : list[str]
        Raw command strings, one per detected shell fence block.
    """

    def __init__(self, cmds: List[str]) -> None:
        self._cmds: List[str] = list(cmds)

    # ------------------------------------------------------------------
    # Container protocol
    # ------------------------------------------------------------------

    def __bool__(self) -> bool:
        """Return ``True`` when at least one command was found."""
        return bool(self._cmds)

    def __iter__(self) -> Iterator[str]:
        """Iterate over the individual command strings."""
        return iter(self._cmds)

    def __len__(self) -> int:
        return len(self._cmds)

    def __repr__(self) -> str:  # pragma: no cover
        return f"ShellCMDs({self._cmds!r})"

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def commands(self) -> List[str]:
        """Return a plain list copy of the captured commands."""
        return list(self._cmds)


# ---------------------------------------------------------------------------
# find_shell_cmds
# ---------------------------------------------------------------------------


def find_shell_cmds(content: str) -> List[str]:
    """
    Parse *content* (an LLM response string) and return every shell command
    block found inside a ``bash``, ``sh``, or ``shell`` fenced code block.

    Each match is stripped of leading/trailing whitespace.  Multiple commands
    separated by newlines within a single block are preserved as a single
    string entry (callers can split on newlines if they need individual lines).

    Parameters
    ----------
    content : str
        The raw text of the LLM response.

    Returns
    -------
    list[str]
        Extracted command strings, one per fenced block.  Empty list if none
        are found.

    Examples
    --------
    >>> text = "Run this:\\n```bash\\npip install reviewforge\\n```"
    >>> find_shell_cmds(text)
    ['pip install reviewforge']
    """
    if not content:
        return []

    cmds: List[str] = []
    for match in _SHELL_FENCE_RE.finditer(content):
        block = match.group(1).strip()
        if block:
            cmds.append(block)

    return cmds
