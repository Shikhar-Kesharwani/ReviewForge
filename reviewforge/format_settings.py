"""
reviewforge/format_settings.py

Settings formatter for ReviewForge.

Provides helpers to render all CLI / config-file settings as a readable
Markdown report and to sanitise that report by redacting sensitive values
(API keys, passwords, tokens, …) before writing or displaying it.
"""

import re
from argparse import _ArgumentGroup  # type: ignore[attr-defined]
from typing import Any


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_settings(parser: Any, args: Any) -> str:
    """Render all ReviewForge settings as a Markdown string.

    Iterates over every argument group registered on *parser*, collects each
    argument's current value from *args*, compares it to the argument default,
    and formats the result into a human-readable Markdown document.

    Parameters
    ----------
    parser:
        A ``configargparse.ArgumentParser`` (or stdlib ``ArgumentParser``)
        instance that owns the argument definitions.
    args:
        The ``Namespace`` returned by ``parser.parse_args()`` (or
        ``parse_known_args()``).

    Returns
    -------
    str
        Multi-line Markdown text suitable for display or writing to a file.
    """
    lines: list[str] = ["# ReviewForge — current settings\n"]

    # Walk every argument group on the parser.
    for group in parser._action_groups:  # noqa: SLF001
        group_title: str = getattr(group, "title", None) or "Options"

        # Collect the arguments that belong to this group, skipping the
        # internal positional/optional catch-all groups that argparse creates.
        group_lines: list[str] = []

        for action in group._group_actions:  # noqa: SLF001
            # Skip hidden / suppressed arguments.
            if action.dest == "==SUPPRESS==":
                continue
            dest: str = action.dest
            if dest == "help":
                continue

            # Resolve current value.
            current_value: Any = getattr(args, dest, None)

            # The first option string is the canonical flag name.
            flag: str = (
                action.option_strings[0]
                if action.option_strings
                else dest
            )

            # Check whether the current value differs from the default.
            default_value: Any = action.default
            is_default: bool = current_value == default_value

            changed_marker: str = "" if is_default else " *(changed)*"

            group_lines.append(
                f"- **`{flag}`** = `{current_value}`{changed_marker}"
            )

        if group_lines:
            lines.append(f"\n## {group_title}\n")
            lines.extend(group_lines)

    return "\n".join(lines)


def scrub_sensitive_info(text: str) -> str:
    """Replace secrets in a settings string with ``***``.

    Detects common patterns such as::

        api_key = sk-abc123
        password = hunter2
        token = ghp_xxxx
        secret = mysecret

    The replacement preserves the key name but hides the value.

    Parameters
    ----------
    text:
        A settings or configuration string that may contain secrets.

    Returns
    -------
    str
        The same string with all detected secret values replaced by ``***``.
    """
    # Pattern explanation:
    #   Group 1 — the key name (api_key, password, token, secret, …)
    #   Separator — optional whitespace, then '=' or ':', then optional whitespace
    #   Group 2 — the value (everything up to the end of the line)
    secret_pattern = re.compile(
        r"(?i)"                               # case-insensitive
        r"((?:api[_-]?key|password|passwd|token|secret|auth[_-]?key"
        r"|access[_-]?key|private[_-]?key|credentials?))"
        r"(\s*[=:]\s*)"                       # separator
        r"([^\s\"'][^\n]*)",                  # the value itself
        re.MULTILINE,
    )
    return secret_pattern.sub(r"\1\2***", text)
