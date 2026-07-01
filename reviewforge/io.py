"""
reviewforge/io.py
-----------------
Terminal InputOutput layer for ReviewForge.

Handles all user-facing terminal interaction:
  - Colored output via Rich (tool messages, errors, warnings, assistant output)
  - Prompt-toolkit powered interactive input with auto-completion and history
  - Streaming LLM response rendering via MarkdownStream
  - Chat and LLM traffic logging to files

Classes
-------
CommandCompletionException
    Raised internally when completion handling needs special routing.

AutoCompleter
    prompt_toolkit Completer implementation that handles /command and
    filename completion.

InputOutput
    The main I/O facade used throughout the ReviewForge application.
"""

from __future__ import annotations

import datetime
import os
import sys
import threading
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import (
    Completer,
    Completion,
    PathCompleter,
    merge_completers,
)
from prompt_toolkit.enums import EditingMode
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory, InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

from .mdstream import MarkdownStream


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def ensure_hash_prefix(color: str | None) -> str | None:
    """
    Ensure a hex color string starts with ``#``.

    Returns the color unchanged if it is None, already starts with ``#``,
    or is a named color (contains only alphabetic chars).

    Examples
    --------
    >>> ensure_hash_prefix("00cc00")
    '#00cc00'
    >>> ensure_hash_prefix("#FF2222")
    '#FF2222'
    >>> ensure_hash_prefix("red")
    'red'
    >>> ensure_hash_prefix(None)
    None
    """
    if color is None:
        return None
    color = color.strip()
    if not color:
        return color
    # Already has a hash, or is a named colour (e.g. "red", "bright_blue")
    if color.startswith("#") or not any(c in color for c in "0123456789abcdefABCDEF"):
        return color
    # Looks like a bare hex string — add the hash
    if all(c in "0123456789abcdefABCDEF" for c in color):
        return f"#{color}"
    return color


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class CommandCompletionException(Exception):
    """
    Raised by completion logic when a /command token needs special routing
    that cannot be handled inline (e.g. redirecting to a different completer).
    """


# ---------------------------------------------------------------------------
# Auto-completer
# ---------------------------------------------------------------------------

# Commands that accept file path arguments
_FILE_ARGUMENT_COMMANDS = {"/add", "/drop", "/read-only"}


class AutoCompleter(Completer):
    """
    A prompt_toolkit ``Completer`` that provides:

    1. **Command completion** — lists all ``/command`` names when the input
       line begins with ``/``.
    2. **Filename completion** — delegates to prompt_toolkit's built-in
       ``PathCompleter`` for commands in ``_FILE_ARGUMENT_COMMANDS``.

    Parameters
    ----------
    commands : list[str]
        All valid slash-command names, e.g. ``["/add", "/drop", "/help"]``.
    rel_fnames : list[str]
        Relative paths of files already tracked in the session.
    addable_rel_fnames : list[str]
        Relative paths of files that *can* be added.
    abs_read_only_fnames : list[str]
        Absolute paths of read-only files.
    root : str
        Repository root directory used as the base for path expansion.
    """

    def __init__(
        self,
        commands: list[str],
        rel_fnames: list[str],
        addable_rel_fnames: list[str],
        abs_read_only_fnames: list[str],
        root: str,
    ) -> None:
        self._commands: list[str] = sorted(commands or [])
        self._rel_fnames: list[str] = rel_fnames or []
        self._addable_rel_fnames: list[str] = addable_rel_fnames or []
        self._abs_read_only_fnames: list[str] = abs_read_only_fnames or []
        self._root: str = root or "."

        # Path completer for filesystem browsing
        self._path_completer = PathCompleter(only_directories=False, expanduser=True)

    # ------------------------------------------------------------------
    # Completer protocol
    # ------------------------------------------------------------------

    def get_completions(
        self,
        document: Any,
        complete_event: Any,
    ) -> Iterable[Completion]:
        """Yield ``Completion`` objects for the current document."""
        text = document.text_before_cursor
        words = text.split()

        # ----------------------------------------------------------------
        # Nothing typed yet or plain text — no completions
        # ----------------------------------------------------------------
        if not text.startswith("/"):
            return

        # ----------------------------------------------------------------
        # Only a "/" so far, or partial command name → complete commands
        # ----------------------------------------------------------------
        if len(words) == 1 and not text.endswith(" "):
            partial = words[0]
            for cmd in self._commands:
                if cmd.startswith(partial):
                    yield Completion(
                        cmd[len(partial):],
                        display=cmd,
                        start_position=0,
                    )
            return

        # ----------------------------------------------------------------
        # Command is complete; check if it accepts file arguments
        # ----------------------------------------------------------------
        command = words[0].lower() if words else ""

        if command in _FILE_ARGUMENT_COMMANDS:
            # Delegate the remainder of the line to path + known-file completion
            yield from self._file_completions(document, text, words)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _file_completions(
        self,
        document: Any,
        text: str,
        words: list[str],
    ) -> Iterable[Completion]:
        """
        Yield completions for file arguments.

        Checks known ``rel_fnames`` and ``addable_rel_fnames`` first, then
        falls back to the filesystem via ``PathCompleter``.
        """
        command = words[0].lower()
        # The partial filename token being typed
        partial = words[-1] if len(words) > 1 and not text.endswith(" ") else ""

        # Pool of candidate filenames depends on the command
        if command == "/drop":
            candidates = self._rel_fnames
        elif command == "/read-only":
            candidates = self._abs_read_only_fnames + self._rel_fnames
        else:
            # /add — offer everything not yet tracked
            candidates = self._addable_rel_fnames

        # Match against known file list
        matched_any = False
        for fname in candidates:
            if fname.startswith(partial):
                matched_any = True
                suffix = fname[len(partial):]
                yield Completion(suffix, display=fname, start_position=0)

        # If no known files matched, fall back to filesystem path completion
        if not matched_any:
            yield from self._path_completer.get_completions(document, complete_event=None)


# ---------------------------------------------------------------------------
# Main InputOutput class
# ---------------------------------------------------------------------------

class InputOutput:
    """
    The primary terminal I/O facade for ReviewForge.

    Wraps Rich for coloured output and prompt_toolkit for interactive input
    with history, auto-completion, and optional multiline editing.

    Parameters
    ----------
    pretty : bool
        When ``True``, output is coloured and markdown is rendered richly.
        Set ``False`` for plain-text / pipe-friendly output.
    yes : bool | None
        If ``True``, all ``confirm_ask`` calls automatically return ``True``.
        If ``False``, they return ``False``.  ``None`` means ask the user.
    input_history_file : str | None
        Path to a file used for persistent readline-style input history.
    chat_history_file : str | None
        Path to a markdown file where all chat exchanges are appended.
    user_input_color : str
        Rich/hex colour for the interactive prompt text.
    tool_output_color : str | None
        Rich/hex colour for tool output messages.
    tool_error_color : str
        Rich/hex colour for error messages.
    tool_warning_color : str
        Rich/hex colour for warning messages.
    assistant_output_color : str
        Rich/hex colour used for the assistant's text when pretty=False.
    code_theme : str
        Pygments theme name for code blocks in markdown (e.g. ``"monokai"``).
    dry_run : bool
        When ``True``, destructive operations are skipped; log only.
    encoding : str
        Text encoding used when writing history files.
    multiline : bool
        Enable multiline input mode (Meta+Enter to submit).
    llm_history_file : str | None
        Path to a file where raw LLM request/response traffic is logged.
    editingmode : str | None
        ``"vi"`` or ``"emacs"`` (default).  Controls prompt_toolkit's editing
        key bindings.
    """

    def __init__(
        self,
        pretty: bool = True,
        yes: bool | None = None,
        input_history_file: str | None = None,
        chat_history_file: str | None = None,
        user_input_color: str = "#00cc00",
        tool_output_color: str | None = None,
        tool_error_color: str = "#FF2222",
        tool_warning_color: str = "#FFA500",
        assistant_output_color: str = "#0088ff",
        code_theme: str = "default",
        dry_run: bool = False,
        encoding: str = "utf-8",
        multiline: bool = False,
        llm_history_file: str | None = None,
        editingmode: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.pretty = pretty
        self.yes = yes
        self.dry_run = dry_run
        self.encoding = encoding
        self.multiline = multiline

        # Normalise hex colours
        self.user_input_color = ensure_hash_prefix(user_input_color)
        self.tool_output_color = ensure_hash_prefix(tool_output_color)
        self.tool_error_color = ensure_hash_prefix(tool_error_color)
        self.tool_warning_color = ensure_hash_prefix(tool_warning_color)
        self.assistant_output_color = ensure_hash_prefix(assistant_output_color)
        self.code_theme = code_theme

        # History files
        self.input_history_file = input_history_file
        self.chat_history_file = chat_history_file
        self.llm_history_file = llm_history_file

        # Thread lock for file writes (multiple threads may log simultaneously)
        self._file_lock = threading.Lock()

        # Rich console — force_terminal=True keeps colour even when piped
        self._console = Console(highlight=False)
        self._err_console = Console(stderr=True, highlight=False)

        # Active MarkdownStream instance (set during streaming, cleared after)
        self._md_stream: MarkdownStream | None = None

        # Editing mode for prompt_toolkit
        if editingmode and editingmode.lower() == "vi":
            self._editing_mode = EditingMode.VI
        else:
            self._editing_mode = EditingMode.EMACS

        # Build the PromptSession (lazy: done on first get_input call)
        self._session: PromptSession | None = None

        # Write session start to chat log
        self._append_chat_history(
            f"\n\n---\n# ReviewForge session — "
            f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

    # ======================================================================
    # Output methods
    # ======================================================================

    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print to the terminal (plain, no colour transformation)."""
        print(*args, **kwargs)

    def tool_output(
        self,
        *msgs: str,
        log_only: bool = False,
        bold: bool = False,
    ) -> None:
        """
        Display an informational tool message.

        Parameters
        ----------
        *msgs :
            Message strings to display (joined with spaces).
        log_only :
            If ``True``, write to the chat log only; do not print.
        bold :
            If ``True``, render the message in bold.
        """
        msg = " ".join(str(m) for m in msgs)
        self._append_chat_history(f"\n> {msg}\n")

        if log_only:
            return

        if self.pretty and self.tool_output_color:
            style = f"bold {self.tool_output_color}" if bold else self.tool_output_color
            self._console.print(msg, style=style)
        elif bold:
            self._console.print(msg, style="bold")
        else:
            self._console.print(msg)

    def tool_error(
        self,
        *msgs: str,
        log_only: bool = False,
        strip_trailing_newline: bool = False,
    ) -> None:
        """
        Display an error message in red.

        Parameters
        ----------
        *msgs :
            Message strings to display (joined with spaces).
        log_only :
            If ``True``, write to the chat log only; do not print.
        strip_trailing_newline :
            If ``True``, strip a trailing newline from the message before
            display (but not before logging).
        """
        msg = " ".join(str(m) for m in msgs)
        self._append_chat_history(f"\n> **ERROR:** {msg}\n")

        if log_only:
            return

        display_msg = msg.rstrip("\n") if strip_trailing_newline else msg

        if self.pretty and self.tool_error_color:
            self._err_console.print(display_msg, style=f"bold {self.tool_error_color}")
        else:
            self._err_console.print(display_msg, style="bold red")

    def tool_warning(
        self,
        *msgs: str,
        log_only: bool = False,
    ) -> None:
        """
        Display a warning message in orange.

        Parameters
        ----------
        *msgs :
            Message strings to display (joined with spaces).
        log_only :
            If ``True``, write to the chat log only; do not print.
        """
        msg = " ".join(str(m) for m in msgs)
        self._append_chat_history(f"\n> **WARNING:** {msg}\n")

        if log_only:
            return

        if self.pretty and self.tool_warning_color:
            self._console.print(msg, style=self.tool_warning_color)
        else:
            self._console.print(msg, style="yellow")

    def assistant_output(self, msg: str, pretty: bool | None = None) -> None:
        """
        Render the assistant's response to the terminal.

        When *pretty* is ``True`` (or inherited from ``self.pretty``), the
        message is rendered as Rich Markdown.  Otherwise it is printed with
        the assistant output colour as plain text.

        Parameters
        ----------
        msg : str
            The full assistant response to display.
        pretty : bool | None
            Override for ``self.pretty``.  Uses instance default when ``None``.
        """
        use_pretty = self.pretty if pretty is None else pretty
        self._append_chat_history(f"\n**Assistant:** {msg}\n")

        if use_pretty:
            mdargs = self.get_assistant_mdargs()
            try:
                md = Markdown(msg, **mdargs)
                self._console.print(md)
            except Exception:
                # Fallback if rendering fails (e.g. corrupted output)
                color = self.assistant_output_color or ""
                style = color if color else "cyan"
                self._console.print(msg, style=style)
        else:
            color = self.assistant_output_color or ""
            style = color if color else "cyan"
            self._console.print(msg, style=style)

    # ======================================================================
    # Streaming output
    # ======================================================================

    def render_incremental_response(self, content: str, final: bool) -> None:
        """
        Render streaming LLM output incrementally using :class:`MarkdownStream`.

        On the first call a new ``MarkdownStream`` is created.  Subsequent
        calls append to it.  When ``final=True`` the stream is closed and the
        reference cleared so the next response starts fresh.

        Parameters
        ----------
        content : str
            The *full* accumulated content so far (not a delta chunk).
            This method computes the delta internally.
        final : bool
            ``True`` when this is the last chunk.
        """
        if self._md_stream is None:
            mdargs = self.get_assistant_mdargs() if self.pretty else {}
            self._md_stream = MarkdownStream(mdargs=mdargs)
            self._md_stream_prev = ""

        # Compute the new delta and update the stream
        delta = content[len(self._md_stream_prev):]
        self._md_stream_prev = content
        self._md_stream.update(delta, final=final)

        if final:
            self._md_stream = None
            self._md_stream_prev = ""
            # Log completed assistant message
            self._append_chat_history(f"\n**Assistant:** {content}\n")

    def get_assistant_mdargs(self) -> dict[str, Any]:
        """
        Return the keyword arguments to pass to ``rich.markdown.Markdown``
        when rendering assistant output.

        Returns
        -------
        dict
            Currently includes ``code_theme`` when set.
        """
        mdargs: dict[str, Any] = {}
        if self.code_theme:
            mdargs["code_theme"] = self.code_theme
        return mdargs

    # ======================================================================
    # Input methods
    # ======================================================================

    def get_input(
        self,
        root: str,
        rel_fnames: list[str],
        addable_rel_fnames: list[str],
        commands: Any,  # Commands object with a .get_names() method
        abs_read_only_fnames: list[str] | None = None,
        edit_format: str | None = None,
    ) -> str:
        """
        Display an interactive prompt and return the user's input string.

        Supports:
        - Persistent file history (if ``input_history_file`` was set)
        - Command and filename auto-completion
        - Multiline editing (Meta+Enter to submit when ``self.multiline=True``)
        - Coloured prompt indicator

        Parameters
        ----------
        root : str
            The repository root path (displayed in the prompt).
        rel_fnames : list[str]
            Relative paths of files currently in the session context.
        addable_rel_fnames : list[str]
            Relative paths of files that can be added.
        commands : object
            An object with a ``.get_names() -> list[str]`` method that returns
            all valid slash-command names.
        abs_read_only_fnames : list[str] | None
            Absolute paths of read-only files.
        edit_format : str | None
            Current edit format (shown in the prompt when set).

        Returns
        -------
        str
            The raw text entered by the user (stripped of leading/trailing
            whitespace).
        """
        abs_read_only_fnames = abs_read_only_fnames or []

        # Determine command names
        if hasattr(commands, "get_names"):
            command_names: list[str] = commands.get_names()
        elif isinstance(commands, (list, tuple)):
            command_names = list(commands)
        else:
            command_names = []

        # Build completer
        completer = AutoCompleter(
            commands=command_names,
            rel_fnames=rel_fnames,
            addable_rel_fnames=addable_rel_fnames,
            abs_read_only_fnames=abs_read_only_fnames,
            root=root,
        )

        # Build or reuse the PromptSession
        session = self._get_session(completer)

        # Build the visual prompt string
        prompt_indicator = self._build_prompt(root, rel_fnames, edit_format)

        try:
            if self.multiline:
                # In multiline mode, Meta+Enter submits; Enter inserts newline
                user_input: str = session.prompt(
                    prompt_indicator,
                    multiline=True,
                    completer=completer,
                )
            else:
                user_input = session.prompt(
                    prompt_indicator,
                    completer=completer,
                )
        except KeyboardInterrupt:
            return ""
        except EOFError:
            # Ctrl-D — signal to the caller that we should exit
            raise

        stripped = user_input.strip()

        # Log user message to chat history
        if stripped:
            self._append_chat_history(f"\n**User:** {stripped}\n")

        return stripped

    def confirm_ask(
        self,
        question: str,
        default: str = "y",
        subject: str | None = None,
        explicit_yes_required: bool = False,
        allow_never: bool = False,
    ) -> bool:
        """
        Ask a yes/no question and return ``True`` for yes, ``False`` for no.

        Respects ``self.yes`` for non-interactive / scripted operation.

        Parameters
        ----------
        question : str
            The question to display.
        default : str
            ``"y"`` or ``"n"`` — the answer used when the user presses Enter.
        subject : str | None
            Optional subject line printed above the question.
        explicit_yes_required : bool
            When ``True``, an empty Enter press is treated as "no" regardless
            of *default*.
        allow_never : bool
            When ``True``, offer an additional ``[N]ever`` option.

        Returns
        -------
        bool
            ``True`` if the user answered yes.
        """
        if subject:
            self._console.print(subject, style="bold")

        # Auto-answer mode
        if self.yes is True:
            answer_display = "y" if not explicit_yes_required else "y (auto)"
            self._console.print(f"{question} {answer_display}")
            self._append_chat_history(f"\n> confirm: {question} → yes (auto)\n")
            return True
        if self.yes is False:
            self._console.print(f"{question} n (auto)")
            self._append_chat_history(f"\n> confirm: {question} → no (auto)\n")
            return False

        # Build prompt suffix like " [Y/n]: " or " [y/N]: "
        if allow_never:
            suffix = " [y/N/never]: "
        elif default.lower() == "y":
            suffix = " [Y/n]: " if not explicit_yes_required else " [y/N]: "
        else:
            suffix = " [y/N]: "

        prompt_text = question + suffix

        while True:
            try:
                raw = input(prompt_text).strip().lower()
            except (KeyboardInterrupt, EOFError):
                return False

            if allow_never and raw in ("never", "nev", "n"):
                self._append_chat_history(f"\n> confirm: {question} → never\n")
                return False

            if raw == "":
                if explicit_yes_required:
                    answer = False
                else:
                    answer = default.lower() == "y"
            elif raw in ("y", "yes"):
                answer = True
            elif raw in ("n", "no"):
                answer = False
            else:
                self._console.print(
                    "Please answer y or n.", style=self.tool_warning_color or "yellow"
                )
                continue

            self._append_chat_history(
                f"\n> confirm: {question} → {'yes' if answer else 'no'}\n"
            )
            return answer

    def prompt_ask(
        self,
        question: str,
        default: str | None = None,
        subject: str | None = None,
    ) -> str:
        """
        Ask a free-text question and return the user's answer.

        Parameters
        ----------
        question : str
            The question to display.
        default : str | None
            Value returned (and shown) when the user presses Enter without
            typing anything.
        subject : str | None
            Optional subject line printed above the question.

        Returns
        -------
        str
            The user's answer (stripped), or *default* if empty.
        """
        if subject:
            self._console.print(subject, style="bold")

        # Show default in square brackets if provided
        suffix = f" [{default}]: " if default else ": "
        prompt_text = question + suffix

        # Auto-answer mode
        if self.yes is not None:
            val = default or ""
            self._console.print(f"{prompt_text}{val}")
            self._append_chat_history(f"\n> prompt: {question} → {val}\n")
            return val

        try:
            raw = input(prompt_text).strip()
        except (KeyboardInterrupt, EOFError):
            return default or ""

        answer = raw if raw else (default or "")
        self._append_chat_history(f"\n> prompt: {question} → {answer}\n")
        return answer

    # ======================================================================
    # LLM traffic logging
    # ======================================================================

    def log_llm_history(self, role: str, content: str) -> None:
        """
        Append a raw LLM message to ``llm_history_file`` (if configured).

        Parameters
        ----------
        role : str
            The message role, e.g. ``"user"``, ``"assistant"``, ``"system"``.
        content : str
            The raw message content.
        """
        if not self.llm_history_file:
            return

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"\n---\n[{timestamp}] **{role.upper()}**\n\n{content}\n"
        self._write_to_file(self.llm_history_file, entry)

    # ======================================================================
    # Internal helpers
    # ======================================================================

    def _get_session(self, completer: Completer) -> PromptSession:
        """
        Return a :class:`PromptSession`, creating it on the first call.

        The session is reused across calls so that history is preserved in
        memory between prompts within the same process.
        """
        if self._session is not None:
            return self._session

        # Set up history backend
        if self.input_history_file:
            try:
                history_path = Path(self.input_history_file)
                history_path.parent.mkdir(parents=True, exist_ok=True)
                history_backend = FileHistory(str(history_path))
            except OSError:
                history_backend = InMemoryHistory()
        else:
            history_backend = InMemoryHistory()

        # Custom key bindings for multiline mode
        bindings = KeyBindings()

        @bindings.add("escape", "enter")
        def _meta_enter(event: Any) -> None:
            """Insert a newline in multiline mode."""
            event.current_buffer.insert_text("\n")

        # Prompt style
        style_dict: dict[str, str] = {}
        if self.user_input_color:
            style_dict["prompt"] = self.user_input_color
        prompt_style = Style.from_dict(style_dict) if style_dict else None

        self._session = PromptSession(
            history=history_backend,
            completer=completer,
            editing_mode=self._editing_mode,
            key_bindings=bindings if self.multiline else None,
            style=prompt_style,
            complete_while_typing=False,
        )
        return self._session

    def _build_prompt(
        self,
        root: str,
        rel_fnames: list[str],
        edit_format: str | None,
    ) -> str:
        """
        Build the visual prompt string shown to the user.

        Example output: ``reviewforge> `` or ``reviewforge [diff]> ``
        """
        base = "reviewforge"
        if edit_format:
            base += f" [{edit_format}]"
        return f"{base}> "

    def _append_chat_history(self, text: str) -> None:
        """Append *text* to the chat history file (if configured)."""
        if not self.chat_history_file:
            return
        self._write_to_file(self.chat_history_file, text)

    def _write_to_file(self, path: str, text: str) -> None:
        """Thread-safe write/append of *text* to *path*."""
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with self._file_lock:
                with file_path.open("a", encoding=self.encoding, errors="replace") as f:
                    f.write(text)
        except OSError as exc:
            # Do not crash the app because of a logging failure
            self._err_console.print(
                f"[io] Could not write to {path}: {exc}",
                style="dim red",
            )
