"""
reviewforge/watch_prompts.py

AI comment patterns and file-watcher configuration for ReviewForge.

The watcher monitors source files for special AI instruction comments.  When
such a comment is detected ReviewForge reads it and either applies code
changes (AI!) or answers a question (AI?).

Usage
-----
Import the constants from this module in the file-watcher component:

    from reviewforge.watch_prompts import (
        AI_COMMENT_PATTERNS,
        AI_CODING_DIRECTIVE_PATTERN,
        WATCH_IGNORE_PATTERNS,
    )
"""

import re
from typing import List

# ---------------------------------------------------------------------------
# AI comment patterns
#
# Each entry is a compiled regex that matches a single-line AI instruction
# comment in a supported programming language.
#
# Captured groups:
#   group(1) — the instruction text following the "ai" keyword
#
# The patterns are intentionally broad: they accept both lower-case "ai" and
# upper-case "AI", and allow any amount of leading whitespace.
# ---------------------------------------------------------------------------

AI_COMMENT_PATTERNS: List[re.Pattern] = [
    # ------------------------------------------------------------------ #
    # Python, Ruby, Shell  (#)
    # ------------------------------------------------------------------ #
    # Matches:  # ai <instruction>
    #           # AI <instruction>
    #           #ai: <instruction>      (colon optional)
    re.compile(
        r"^\s*#\s*[Aa][Ii]:?\s+(.+)$",
        re.MULTILINE,
    ),

    # ------------------------------------------------------------------ #
    # JavaScript, C, C++, Java, Go, Rust, Swift, Kotlin  (//)
    # ------------------------------------------------------------------ #
    # Matches:  // ai <instruction>
    #           // AI <instruction>
    re.compile(
        r"^\s*//\s*[Aa][Ii]:?\s+(.+)$",
        re.MULTILINE,
    ),

    # ------------------------------------------------------------------ #
    # SQL, Haskell, Lua (line comments with --)
    # ------------------------------------------------------------------ #
    # Matches:  -- ai <instruction>
    #           -- AI <instruction>
    re.compile(
        r"^\s*--\s*[Aa][Ii]:?\s+(.+)$",
        re.MULTILINE,
    ),

    # ------------------------------------------------------------------ #
    # HTML / XML  (<!-- ... -->)
    # ------------------------------------------------------------------ #
    # Matches:  <!-- ai <instruction> -->
    #           <!-- AI <instruction>-->
    re.compile(
        r"<!--\s*[Aa][Ii]:?\s+(.+?)\s*-->",
        re.DOTALL,
    ),

    # ------------------------------------------------------------------ #
    # Lua / Assembly (semicolon)
    # ------------------------------------------------------------------ #
    # Matches:  ; ai <instruction>
    #           ; AI <instruction>
    re.compile(
        r"^\s*;\s*[Aa][Ii]:?\s+(.+)$",
        re.MULTILINE,
    ),

    # ------------------------------------------------------------------ #
    # CSS / SCSS  (/* ... */)
    # ------------------------------------------------------------------ #
    # Matches:  /* ai <instruction> */
    #           /* AI <instruction>*/
    re.compile(
        r"/\*\s*[Aa][Ii]:?\s+(.+?)\s*\*/",
        re.DOTALL,
    ),

    # ------------------------------------------------------------------ #
    # Batch / Windows INI  (REM or ::)
    # ------------------------------------------------------------------ #
    # Matches:  REM ai <instruction>
    #           :: ai <instruction>
    re.compile(
        r"^\s*(?:REM|::)\s+[Aa][Ii]:?\s+(.+)$",
        re.MULTILINE | re.IGNORECASE,
    ),
]


# ---------------------------------------------------------------------------
# AI coding directive pattern
#
# Distinguishes between two flavours of AI comment:
#
#   AI!  — a directive: the model should apply changes to the code
#   AI?  — a query:     the model should answer a question
#
# The pattern matches the directive marker and captures:
#   group("marker") — "!" or "?"
#   group("text")   — the instruction / question text
#
# Supported comment styles: #, //, --, ;
# ---------------------------------------------------------------------------

AI_CODING_DIRECTIVE_PATTERN: re.Pattern = re.compile(
    r"""
    ^\s*                    # optional leading whitespace
    (?:                     # comment opener (non-capturing)
        \#                  # Python / Ruby / Shell
      | //                  # JS / C / Java / etc.
      | --                  # SQL / Haskell
      | ;                   # Lua / Assembly / INI
    )
    \s*                     # space between comment char and keyword
    AI                      # literal "AI" (case-sensitive: directives are upper)
    (?P<marker>[!?])        # ! = change directive, ? = query
    \s*:?\s*                # optional colon separator
    (?P<text>.+?)           # the instruction text (non-greedy)
    \s*$                    # trailing whitespace / end of line
    """,
    re.VERBOSE | re.MULTILINE,
)


# ---------------------------------------------------------------------------
# Watch ignore patterns
#
# The file-watcher skips any path that matches one of these glob-style
# strings.  Patterns ending in '/' indicate directories.
# ---------------------------------------------------------------------------

WATCH_IGNORE_PATTERNS: List[str] = [
    # Version control
    ".git/",
    ".hg/",
    ".svn/",

    # Python artefacts
    "__pycache__/",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".mypy_cache/",
    ".ruff_cache/",
    ".pytest_cache/",
    "*.egg-info/",
    "dist/",
    "build/",
    ".eggs/",
    ".tox/",
    ".venv/",
    "venv/",
    "env/",
    ".env/",

    # JavaScript / Node
    "node_modules/",
    ".npm/",
    ".yarn/",
    "*.min.js",
    "*.bundle.js",
    "*.map",

    # IDE and editor files
    ".idea/",
    ".vscode/",
    "*.swp",
    "*.swo",
    "*~",

    # Operating system
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",

    # Compiled / binary outputs
    "*.so",
    "*.dll",
    "*.dylib",
    "*.exe",
    "*.o",
    "*.a",
    "*.lib",

    # Logs and temporary files
    "*.log",
    "*.tmp",
    "*.bak",
    "*.orig",

    # Test coverage
    ".coverage",
    "htmlcov/",
    "coverage.xml",

    # Documentation build artefacts
    "_build/",
    "site/",
    "docs/_build/",

    # Jupyter
    ".ipynb_checkpoints/",

    # ReviewForge internal
    ".reviewforge/",
]
