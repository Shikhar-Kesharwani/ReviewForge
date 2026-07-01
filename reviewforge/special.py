"""
reviewforge/special.py

Filters important source files from a repository file list.

ReviewForge focuses its analysis on source-code files that are likely to
contain reviewer-relevant content.  This module defines the patterns that
classify files as "important" or "ignorable" and provides filter helpers
based on those patterns.
"""

import fnmatch
import os
from typing import List


# ---------------------------------------------------------------------------
# Pattern lists
# ---------------------------------------------------------------------------

#: File glob patterns that are considered *important* for code review.
#: Files matching at least one of these patterns (and not excluded by
#: :data:`IGNORE_PATTERNS`) will be retained by :func:`filter_important_files`.
IMPORTANT_PATTERNS: List[str] = [
    "*.py",
    "*.js",
    "*.ts",
    "*.tsx",
    "*.jsx",
    "*.go",
    "*.rs",
    "*.java",
    "*.cpp",
    "*.cc",
    "*.cxx",
    "*.c",
    "*.h",
    "*.hpp",
    "*.cs",
    "*.rb",
    "*.php",
    "*.swift",
    "*.kt",
    "*.scala",
    "*.sh",
    "*.bash",
    "Makefile",
    "CMakeLists.txt",
    "package.json",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Cargo.toml",
    "go.mod",
    "go.sum",
    "requirements.txt",
    "requirements*.txt",
    "Dockerfile",
    "docker-compose*.yml",
    "*.yaml",
    "*.yml",
    "*.toml",
    "*.json",
    "*.md",
    "*.rst",
]

#: Glob patterns for paths that should **always** be excluded from analysis,
#: even if they would otherwise match an entry in :data:`IMPORTANT_PATTERNS`.
IGNORE_PATTERNS: List[str] = [
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "__pycache__",
    ".git",
    ".git/*",
    ".gitignore",
    "node_modules",
    "node_modules/*",
    ".venv",
    ".venv/*",
    "venv",
    "venv/*",
    "env",
    "env/*",
    ".env",
    "*.log",
    "*.tmp",
    "*.temp",
    ".DS_Store",
    "Thumbs.db",
    "*.egg-info",
    "*.egg-info/*",
    "dist",
    "dist/*",
    "build",
    "build/*",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "*.min.js",
    "*.min.css",
    "*.lock",
]

# ---------------------------------------------------------------------------
# Source-file extension set (for fast lookup in is_source_file)
# ---------------------------------------------------------------------------

_SOURCE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py", ".js", ".ts", ".tsx", ".jsx",
        ".go", ".rs", ".java",
        ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp",
        ".cs", ".rb", ".php", ".swift", ".kt", ".scala",
        ".sh", ".bash", ".zsh", ".fish",
        ".lua", ".r", ".jl", ".ex", ".exs",
        ".hs", ".ml", ".mli", ".clj", ".cljs",
        ".dart", ".erl", ".elm",
    }
)


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def _matches_any(name: str, patterns: List[str]) -> bool:
    """Return True if *name* (basename) matches any pattern in *patterns*."""
    for pat in patterns:
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def _path_has_ignored_component(fpath: str) -> bool:
    """Return True if any path component of *fpath* matches IGNORE_PATTERNS."""
    parts = fpath.replace("\\", "/").split("/")
    for part in parts:
        if _matches_any(part, IGNORE_PATTERNS):
            return True
    return False


def filter_important_files(fnames: List[str]) -> List[str]:
    """Filter *fnames* to only include important source-code files.

    A file is retained when **all** of the following hold:

    1. Its basename (or full relative path) matches at least one pattern in
       :data:`IMPORTANT_PATTERNS`.
    2. No component of its path matches any pattern in :data:`IGNORE_PATTERNS`.

    Parameters
    ----------
    fnames:
        A list of file paths (absolute or relative).

    Returns
    -------
    list[str]
        The subset of *fnames* that passed the filter, in the same order.
    """
    result: List[str] = []
    for fpath in fnames:
        basename = os.path.basename(fpath)

        # Exclude if any path component is ignored.
        if _path_has_ignored_component(fpath):
            continue

        # Include only if basename matches an important pattern.
        if _matches_any(basename, IMPORTANT_PATTERNS):
            result.append(fpath)

    return result


def is_source_file(fname: str) -> bool:
    """Return *True* if *fname* has a recognised source-code file extension.

    Parameters
    ----------
    fname:
        File path or bare filename to test.

    Returns
    -------
    bool
        ``True`` when the file extension is in the known source-extension set.

    Example
    -------
    >>> is_source_file("main.py")
    True
    >>> is_source_file("README.md")
    False
    """
    _, ext = os.path.splitext(fname)
    return ext.lower() in _SOURCE_EXTENSIONS
