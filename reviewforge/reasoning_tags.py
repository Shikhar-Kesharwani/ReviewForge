"""
reviewforge/reasoning_tags.py

Utilities for stripping chain-of-thought / reasoning tags from LLM responses.

Some models (e.g. DeepSeek-R1, Claude with extended thinking) wrap their
internal reasoning in XML-style tags such as <think>...</think>.  This module
provides tools to detect and remove those sections so callers receive only the
final answer.
"""

import re
from typing import Optional, Tuple


class ReasoningTagStripper:
    """Strip a specific reasoning / thinking tag from LLM output.

    Parameters
    ----------
    tag:
        The tag name to strip, *without* angle-brackets.  Defaults to
        ``'think'`` which handles ``<think>...</think>`` blocks.

    Example
    -------
    >>> stripper = ReasoningTagStripper()
    >>> clean = stripper.strip_reasoning("<think>let me reason</think>Answer!")
    >>> assert clean == "Answer!"
    """

    def __init__(self, tag: str = "think") -> None:
        self.tag = tag
        # Pre-compile the regex for performance.
        # DOTALL so '.' matches newlines; we strip all whitespace around the
        # tag block so the returned text doesn't start with an empty line.
        self._pattern = re.compile(
            r"\s*<" + re.escape(tag) + r">.*?</" + re.escape(tag) + r">\s*",
            re.DOTALL,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def strip_reasoning(self, text: str) -> str:
        """Return *text* with all ``<tag>…</tag>`` blocks removed.

        Leading/trailing whitespace that only existed because of the removed
        block is also cleaned up so the result reads naturally.

        Parameters
        ----------
        text:
            The raw LLM response string that may contain reasoning blocks.

        Returns
        -------
        str
            The cleaned response with reasoning sections excised.
        """
        cleaned = self._pattern.sub("", text)
        return cleaned.strip()


# ---------------------------------------------------------------------------
# Standalone helper functions
# ---------------------------------------------------------------------------


def has_reasoning_tag(text: str, tag: str = "think") -> bool:
    """Return *True* if *text* contains a ``<tag>…</tag>`` reasoning block.

    Parameters
    ----------
    text:
        The string to inspect.
    tag:
        Tag name to look for (default ``'think'``).

    Returns
    -------
    bool
        ``True`` when the opening tag ``<tag>`` is present in *text*.
    """
    opening = f"<{tag}>"
    return opening in text


def remove_reasoning_tag(
    text: str, tag: str = "think"
) -> Tuple[str, Optional[str]]:
    """Strip ``<tag>…</tag>`` from *text* and return both parts.

    Parameters
    ----------
    text:
        The raw LLM response.
    tag:
        Tag name to remove (default ``'think'``).

    Returns
    -------
    tuple[str, str | None]
        A ``(cleaned_text, extracted_reasoning)`` pair.

        * ``cleaned_text`` — the response with the reasoning block removed and
          surrounding whitespace trimmed.
        * ``extracted_reasoning`` — the text that was *inside* the tag, or
          ``None`` if no such tag was found in *text*.

    Example
    -------
    >>> clean, reasoning = remove_reasoning_tag("<think>why?</think>Sure!")
    >>> clean
    'Sure!'
    >>> reasoning
    'why?'
    """
    pattern = re.compile(
        r"\s*<"
        + re.escape(tag)
        + r">(.*?)</"
        + re.escape(tag)
        + r">\s*",
        re.DOTALL,
    )
    match = pattern.search(text)
    if match is None:
        return text, None

    extracted_reasoning: str = match.group(1).strip()
    cleaned_text: str = pattern.sub("", text).strip()
    return cleaned_text, extracted_reasoning
