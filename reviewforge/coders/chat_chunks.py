"""
reviewforge/coders/chat_chunks.py

Message chunk management for ReviewForge LLM conversations.

A conversation is split into named "chunks" that are assembled in a specific
order before being sent to the LLM.  This makes it easy to slot in repo-map
context, read-only files, or editable file contents without manually managing
raw message lists everywhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# We import sendchat lazily inside get_llm_messages to avoid circular imports.


@dataclass
class ChatChunks:
    """
    Holds the distinct segments of a multi-turn LLM conversation.

    Attributes
    ----------
    system : list
        The system message(s).  Typically a single dict with role="system".
    examples : list
        Few-shot example messages injected right after the system prompt.
    done : list
        Completed conversation turns (prior user/assistant pairs).
    repo : list
        Message(s) containing the repository map (if any).
    readonly : list
        Message(s) with read-only file contents the LLM may reference but
        must not edit.
    files : list
        Message(s) with the editable file contents the LLM may modify.
    cur : list
        The current (in-progress) conversation turn — i.e., the latest user
        message and any partial assistant reply.
    """

    system: list = field(default_factory=list)
    examples: list = field(default_factory=list)
    done: list = field(default_factory=list)
    repo: list = field(default_factory=list)
    readonly: list = field(default_factory=list)
    files: list = field(default_factory=list)
    cur: list = field(default_factory=list)

    # ------------------------------------------------------------------
    # Message assembly
    # ------------------------------------------------------------------

    def all_messages(self) -> List[dict]:
        """
        Assemble all chunks into a flat, ordered list of messages ready to
        send to the LLM.

        Ordering:
          1. system      – model identity / instructions
          2. examples    – few-shot demonstrations
          3. done        – historical conversation turns
          4. repo        – repo-map context   ┐
          5. readonly    – read-only files    │  interleaved as a single
          6. files       – editable files     │  contextual block appended
          7. cur         – current user turn  ┘  after the history

        Returns
        -------
        list[dict]
            Flat list of ``{"role": "...", "content": "..."}`` dicts.
        """
        messages: List[dict] = []

        messages.extend(self.system)
        messages.extend(self.examples)
        messages.extend(self.done)

        # Context block: repo map + read-only + editable files + current turn
        messages.extend(self.repo)
        messages.extend(self.readonly)
        messages.extend(self.files)
        messages.extend(self.cur)

        return messages

    # ------------------------------------------------------------------
    # LLM-ready message list
    # ------------------------------------------------------------------

    def get_llm_messages(self) -> List[dict]:
        """
        Return the full message list, post-processed so that roles strictly
        alternate (user → assistant → user → …).

        ``sendchat.ensure_alternating_roles`` merges consecutive messages with
        the same role by concatenating their content, which is required by most
        LLM APIs.

        Returns
        -------
        list[dict]
            Alternating-role message list safe to pass directly to the chat API.
        """
        from reviewforge.sendchat import ensure_alternating_roles  # noqa: PLC0415

        raw = self.all_messages()
        return ensure_alternating_roles(raw)


# ---------------------------------------------------------------------------
# Module-level convenience wrappers (keep backward-compat if callers use them
# as plain functions rather than methods)
# ---------------------------------------------------------------------------


def all_messages(chunks: ChatChunks) -> List[dict]:
    """Functional wrapper around :py:meth:`ChatChunks.all_messages`."""
    return chunks.all_messages()


def get_llm_messages(chunks: ChatChunks) -> List[dict]:
    """Functional wrapper around :py:meth:`ChatChunks.get_llm_messages`."""
    return chunks.get_llm_messages()
