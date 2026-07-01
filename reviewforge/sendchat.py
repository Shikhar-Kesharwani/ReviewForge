"""
reviewforge/sendchat.py
~~~~~~~~~~~~~~~~~~~~~~~
LiteLLM message-sending utilities for ReviewForge.

This module provides a thin, retry-aware wrapper around ``litellm.completion``
and a set of helper functions for pre-processing message lists before they are
sent to an LLM endpoint.

Public API
----------
- send_with_retries        -- raw completion call with exponential back-off
- simple_send_with_retries -- like above but returns just the reply text
- ensure_alternating_roles -- merge consecutive same-role messages
- sanity_check_messages    -- validate a message list before sending
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from reviewforge.llm import (
    _TRANSIENT_EXCEPTIONS,
    litellm,
    retry_on_transient_error,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------

Message = Dict[str, str]   # {"role": "user" | "assistant" | "system", "content": str}


# ---------------------------------------------------------------------------
# Core send helper
# ---------------------------------------------------------------------------

def send_with_retries(
    model_name: str,
    messages: List[Message],
    temperature: float = 0,
    stream: bool = False,
    **kwargs: Any,
) -> Any:
    """Call ``litellm.completion`` with automatic exponential back-off.

    Any extra keyword arguments are forwarded verbatim to
    ``litellm.completion``, so callers can pass ``max_tokens``, ``top_p``,
    etc.

    Parameters
    ----------
    model_name:
        Full LiteLLM model string, e.g. ``"gemini/gemini-2.0-flash"`` or
        ``"gpt-4o"``.
    messages:
        A list of chat-format message dicts (``role`` + ``content``).
    temperature:
        Sampling temperature (0 = greedy / deterministic).
    stream:
        When *True*, returns a streaming iterator instead of a complete
        response object.
    **kwargs:
        Additional keyword arguments forwarded to ``litellm.completion``.

    Returns
    -------
    litellm.ModelResponse | Generator
        The raw completion object returned by LiteLLM, or a streaming
        generator when ``stream=True``.

    Raises
    ------
    litellm.exceptions.APIError
        Re-raised after all retry attempts have been exhausted.
    """

    @retry_on_transient_error(max_tries=5, max_time=120.0)
    def _call() -> Any:
        logger.debug(
            "send_with_retries: model=%s, messages=%d, stream=%s",
            model_name,
            len(messages),
            stream,
        )
        return litellm.completion(
            model=model_name,
            messages=messages,
            temperature=temperature,
            stream=stream,
            **kwargs,
        )

    return _call()


# ---------------------------------------------------------------------------
# Convenience wrapper that extracts just the text content
# ---------------------------------------------------------------------------

def simple_send_with_retries(
    model_name: str,
    messages: List[Message],
    **kwargs: Any,
) -> Optional[str]:
    """Send *messages* and return only the reply text from the first choice.

    This is a convenience wrapper around :func:`send_with_retries`.  It
    extracts ``choices[0].message.content`` from the completion response and
    returns it as a plain string.

    Parameters
    ----------
    model_name:
        Full LiteLLM model string.
    messages:
        Chat-format message list.
    **kwargs:
        Forwarded to :func:`send_with_retries` (and on to
        ``litellm.completion``).

    Returns
    -------
    str | None
        The assistant reply text, or *None* if the response could not be
        parsed (e.g. content-filtering / empty response).
    """
    try:
        response = send_with_retries(
            model_name=model_name,
            messages=messages,
            **kwargs,
        )
        content: Optional[str] = response.choices[0].message.content
        return content
    except _TRANSIENT_EXCEPTIONS:
        # All retries exhausted -- caller decides how to handle.
        raise
    except (AttributeError, IndexError, KeyError) as exc:
        logger.warning(
            "simple_send_with_retries: failed to extract text from response: %s",
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Message-list pre-processing helpers
# ---------------------------------------------------------------------------

def ensure_alternating_roles(messages: List[Message]) -> List[Message]:
    """Merge consecutive messages that share the same role.

    Most LLM providers require that ``user`` and ``assistant`` turns strictly
    alternate.  When ReviewForge constructs a conversation programmatically it
    may end up with two consecutive ``user`` messages; this function collapses
    them by concatenating their ``content`` fields with a newline separator.

    ``system`` messages at the very beginning of the list are always kept
    unchanged and are not merged with subsequent messages.

    Parameters
    ----------
    messages:
        Input message list, potentially containing consecutive same-role items.

    Returns
    -------
    list[Message]
        A new list where no two adjacent messages share the same role
        (except that a leading ``system`` message is treated separately).

    Examples
    --------
    >>> msgs = [
    ...     {"role": "user", "content": "Hello"},
    ...     {"role": "user", "content": "How are you?"},
    ...     {"role": "assistant", "content": "I'm fine."},
    ... ]
    >>> ensure_alternating_roles(msgs)
    [
        {"role": "user", "content": "Hello\nHow are you?"},
        {"role": "assistant", "content": "I'm fine."},
    ]
    """
    if not messages:
        return []

    result: List[Message] = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Always keep extra keys (e.g. "name", tool call info).
        extra = {k: v for k, v in msg.items() if k not in ("role", "content")}

        if (
            result
            and result[-1]["role"] == role
            # System messages should not be merged with each other or with
            # non-system messages.
            and role != "system"
        ):
            # Merge by appending content to the last message.
            separator = "\n" if result[-1]["content"] else ""
            result[-1]["content"] = result[-1]["content"] + separator + content
        else:
            new_msg: Message = {"role": role, "content": content}
            new_msg.update(extra)
            result.append(new_msg)

    return result


def sanity_check_messages(messages: List[Message]) -> List[str]:
    """Validate a message list and return a list of warning strings.

    Checks that *messages* forms a plausible LLM conversation:

    * The list is non-empty.
    * Only recognised roles (``system``, ``user``, ``assistant``) are used.
    * At most one ``system`` message exists and it appears first.
    * After the optional system message, roles alternate between ``user``
      and ``assistant``.
    * The last message has the role ``user`` (i.e. the model has not already
      replied).

    Parameters
    ----------
    messages:
        The message list to validate.

    Returns
    -------
    list[str]
        A (possibly empty) list of human-readable warning strings describing
        any issues found.  An empty list means the messages look valid.
    """
    warnings: List[str] = []
    valid_roles = {"system", "user", "assistant"}

    if not messages:
        warnings.append("Message list is empty.")
        return warnings

    # Check roles.
    for i, msg in enumerate(messages):
        role = msg.get("role")
        if role not in valid_roles:
            warnings.append(
                f"Message {i} has unknown role {role!r}; "
                f"expected one of {sorted(valid_roles)}."
            )

    # Separate optional leading system message.
    idx = 0
    if messages[0].get("role") == "system":
        idx = 1

    # Check for extra system messages after position 0.
    for i, msg in enumerate(messages[idx:], start=idx):
        if msg.get("role") == "system":
            warnings.append(
                f"System message found at position {i} (only position 0 is valid)."
            )

    # Validate alternating user/assistant from idx onward.
    conversation = messages[idx:]
    if not conversation:
        warnings.append("No user/assistant messages found (only a system message).")
        return warnings

    if conversation[0].get("role") != "user":
        warnings.append(
            f"First user/assistant message has role {conversation[0].get('role')!r}; "
            "expected 'user'."
        )

    for i in range(1, len(conversation)):
        prev_role = conversation[i - 1].get("role")
        curr_role = conversation[i].get("role")
        if prev_role == curr_role:
            warnings.append(
                f"Consecutive messages with the same role {curr_role!r} "
                f"at positions {idx + i - 1} and {idx + i}."
            )

    # The last message should be from the user.
    last_role = conversation[-1].get("role")
    if last_role != "user":
        warnings.append(
            f"Last message has role {last_role!r}; expected 'user' "
            "(the model should not have replied yet)."
        )

    return warnings


# ---------------------------------------------------------------------------
# Module public surface
# ---------------------------------------------------------------------------

__all__ = [
    "send_with_retries",
    "simple_send_with_retries",
    "ensure_alternating_roles",
    "sanity_check_messages",
]
