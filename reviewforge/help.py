"""
reviewforge/help.py

Built-in help system for ReviewForge.

Provides:
  - HELP_TEXT     — a dict mapping slash-command names to concise descriptions
  - Help          — a class that can answer user questions from bundled docs
  - install_help_extra(io) — placeholder for additional doc installation
"""

from pathlib import Path
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Command help strings
# ---------------------------------------------------------------------------

HELP_TEXT: Dict[str, str] = {
    # ---- File management -----------------------------------------------
    "/add": (
        "Add one or more files to the review context so ReviewForge can read "
        "and modify them.  Supports glob patterns, e.g. /add src/**/*.py."
    ),
    "/drop": (
        "Remove files from the active context.  The files are not deleted — "
        "they are simply excluded from the next review pass."
    ),
    "/ls": (
        "List all files currently in the review context together with their "
        "approximate token usage."
    ),
    "/read-only": (
        "Add files to the context in read-only mode.  ReviewForge can read "
        "them for background information but will not edit them."
    ),
    "/diff": (
        "Show a unified diff of all changes ReviewForge has made since the "
        "last /commit or session start."
    ),
    # ---- Git operations -----------------------------------------------
    "/commit": (
        "Commit all ReviewForge-applied edits to git with an auto-generated "
        "commit message.  Equivalent to 'git commit -a -m <msg>'."
    ),
    "/undo": (
        "Undo the last commit made by ReviewForge via 'git reset --soft HEAD~'."
    ),
    "/git": (
        "Run an arbitrary git command inside the project repository and print "
        "its output, e.g. /git log --oneline -10."
    ),
    # ---- Model / provider --------------------------------------------
    "/model": (
        "Switch the active LLM model mid-session, e.g. /model gpt-4o. "
        "Accepts the same model strings as the --model CLI flag."
    ),
    "/models": (
        "List all model names that ReviewForge can connect to, grouped by "
        "provider."
    ),
    "/weak-model": (
        "Set the weaker/cheaper model used for lightweight sub-tasks such as "
        "commit message generation."
    ),
    # ---- Review commands --------------------------------------------
    "/review": (
        "Trigger a code review pass on all files currently in context.  "
        "ReviewForge will comment on style, bugs, and improvement opportunities."
    ),
    "/fix": (
        "Ask ReviewForge to automatically fix the issues it identified in the "
        "most recent review.  Changes are shown as a diff before being applied."
    ),
    "/explain": (
        "Ask ReviewForge to explain a specific piece of code.  Accepts a file "
        "path and optional line range, e.g. /explain main.py:10-40."
    ),
    "/refactor": (
        "Request a focused refactoring of the specified file or function, "
        "keeping behaviour identical while improving readability."
    ),
    "/test": (
        "Generate unit tests for the code currently in context and place them "
        "in a test file alongside the source."
    ),
    "/lint": (
        "Run the configured linters (ruff, eslint, etc.) on the files in "
        "context and show a summary of findings."
    ),
    # ---- Session control ----------------------------------------
    "/ask": (
        "Ask ReviewForge an open-ended question without triggering any edits. "
        "Useful for explanations and design advice."
    ),
    "/chat-mode": (
        "Switch between 'code' mode (can edit files) and 'ask' mode (read-only "
        "Q&A) for the current session."
    ),
    "/clear": (
        "Clear the conversation history and start a fresh session, while "
        "keeping the current file context."
    ),
    "/reset": (
        "Clear both the conversation history and the file context, returning "
        "ReviewForge to its initial state."
    ),
    "/copy": (
        "Copy the last LLM response to the system clipboard."
    ),
    "/paste": (
        "Paste text from the clipboard directly into the ReviewForge prompt, "
        "useful for sharing code snippets from other editors."
    ),
    # ---- Tokens & cost ------------------------------------------
    "/tokens": (
        "Show a breakdown of token usage for each file in context, the "
        "current conversation, and the model's context-window limit."
    ),
    "/cost": (
        "Display the cumulative cost of the current session based on the "
        "provider's published token pricing."
    ),
    # ---- Configuration ------------------------------------------
    "/settings": (
        "Open the ReviewForge configuration file (~/.reviewforge/config.yml) "
        "for editing, or display the effective settings when given no args."
    ),
    "/editor": (
        "Set or display the preferred text editor that ReviewForge opens for "
        "multi-line input."
    ),
    # ---- Utilities ----------------------------------------------
    "/run": (
        "Execute a shell command and optionally feed its output back to the "
        "LLM for analysis, e.g. /run pytest --tb=short."
    ),
    "/map": (
        "Show a high-level structural map of the repository: classes, "
        "functions, and important symbols — produced by the repo-map engine."
    ),
    "/map-refresh": (
        "Force a re-scan of the repository tree-sitter map, picking up new "
        "files and symbols without restarting ReviewForge."
    ),
    "/web": (
        "Fetch a URL and add its text content to the current context so "
        "ReviewForge can reference it in its responses."
    ),
    "/voice": (
        "Activate the voice input mode.  ReviewForge listens for spoken "
        "instructions and transcribes them via the configured STT backend."
    ),
    # ---- Help & diagnostics ------------------------------------
    "/help": (
        "Display this command reference.  Pass a command name for detailed "
        "usage, e.g. /help /add."
    ),
    "/version": (
        "Print the installed ReviewForge version and check PyPI for updates."
    ),
    "/upgrade": (
        "Upgrade ReviewForge to the latest version from PyPI in-place using pip."
    ),
    "/report": (
        "Open a pre-filled GitHub issue in your browser to report a bug or "
        "unexpected behaviour."
    ),
    "/exit": (
        "Exit ReviewForge cleanly, writing the session history to the log file "
        "if logging is enabled."
    ),
    "/quit": "Alias for /exit.",
}


# ---------------------------------------------------------------------------
# Help class
# ---------------------------------------------------------------------------

class Help:
    """
    Built-in help system for ReviewForge.

    Optionally indexes a list of documentation files so it can provide
    context-aware answers.  When no doc files are indexed, ``ask()`` falls
    back to the static ``HELP_TEXT`` table and points users to the README.

    Parameters
    ----------
    fnames : list[str | Path] | None
        Optional list of documentation file paths to index.  Each file is
        read and stored for simple keyword matching.
    """

    def __init__(self, fnames: Optional[List] = None):
        self._doc_index: Dict[str, str] = {}

        if fnames:
            for path in fnames:
                try:
                    text = Path(path).read_text(encoding="utf-8", errors="replace")
                    self._doc_index[str(path)] = text
                except OSError:
                    pass  # skip unreadable files

    # ------------------------------------------------------------------

    def ask(self, question: str, io) -> str:
        """
        Answer a question about ReviewForge.

        If documentation files have been indexed, performs a simple
        case-insensitive keyword search and returns the surrounding paragraph.
        Otherwise returns a helpful fallback pointing to the README and GitHub.

        Parameters
        ----------
        question : str
            The user's question, e.g. "how do I add files to context?".
        io       : reviewforge IO object
            Must expose ``tool_output(msg)``.

        Returns
        -------
        str
            A human-readable answer.
        """
        # 1. Check HELP_TEXT for a matching command
        q_lower = question.lower().strip()
        for cmd, description in HELP_TEXT.items():
            if cmd.lower().lstrip("/") in q_lower or q_lower.startswith(cmd.lower()):
                answer = f"**{cmd}** — {description}"
                io.tool_output(answer)
                return answer

        # 2. Search indexed doc files
        if self._doc_index:
            hits = []
            words = [w for w in q_lower.split() if len(w) > 3]
            for path, content in self._doc_index.items():
                content_lower = content.lower()
                if any(w in content_lower for w in words):
                    # Find the paragraph containing the first hit
                    idx = -1
                    for w in words:
                        idx = content_lower.find(w)
                        if idx != -1:
                            break
                    if idx != -1:
                        start = max(0, idx - 200)
                        end = min(len(content), idx + 400)
                        excerpt = content[start:end].strip()
                        hits.append(f"*From {Path(path).name}:*\n\n{excerpt}")

            if hits:
                answer = "\n\n---\n\n".join(hits[:3])
                io.tool_output(answer)
                return answer

        # 3. Fallback
        fallback = (
            "I don't have a specific answer for that question.\n\n"
            "Here are some resources that may help:\n"
            "  • README: https://github.com/Shikhar/reviewforge#readme\n"
            "  • GitHub Issues: https://github.com/Shikhar/reviewforge/issues\n"
            "  • Slash-command reference: type /help inside ReviewForge\n\n"
            "You can also type /help <command> for detailed usage of any command."
        )
        io.tool_output(fallback)
        return fallback


# ---------------------------------------------------------------------------
# Extras
# ---------------------------------------------------------------------------

def install_help_extra(io) -> None:
    """
    Placeholder for installing additional help documentation.

    In a future release this will download the full ReviewForge docs and index
    them locally so that ``Help.ask()`` can answer detailed questions.

    Parameters
    ----------
    io : reviewforge IO object
        Must expose ``tool_output(msg)``.
    """
    io.tool_output(
        "Additional help documentation is not yet available for download.\n"
        "Full docs are planned for a future release.\n"
        "In the meantime, visit: https://github.com/Shikhar/reviewforge#readme"
    )
