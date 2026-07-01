"""
reviewforge/coders/search_replace.py

Core SEARCH/REPLACE edit-block parser and applier for ReviewForge.

The LLM outputs code edits in this format:

    filename.py
    ```python
    <<<<<<< SEARCH
    old code here
    =======
    new code here
    >>>>>>> REPLACE
    ```

This module is responsible for:
  1. Parsing that format out of raw LLM response text.
  2. Applying the parsed edits to in-memory file content strings.
  3. Writing edited content back to disk (with optional dry-run).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Optional fuzzy-match dependency
# ---------------------------------------------------------------------------
try:
    from diff_match_patch import diff_match_patch as _DiffMatchPatch

    _HAS_DMP = True
except ImportError:  # pragma: no cover
    _HAS_DMP = False


# ---------------------------------------------------------------------------
# Constants / markers
# ---------------------------------------------------------------------------

SEARCH_MARKER = "<<<<<<< SEARCH"
DIVIDER_MARKER = "======="
REPLACE_MARKER = ">>>>>>> REPLACE"

# Language hints we accept on fences but otherwise ignore for edit-block logic
_FENCE_LANGUAGES = r"(?:python|py|js|ts|tsx|jsx|java|c|cpp|cs|go|rs|rb|sh|bash|shell|html|css|json|yaml|yml|toml|sql|md|txt|)?"

# Matches the opening ``` fence (with an optional language hint)
_FENCE_OPEN_RE = re.compile(r"^```" + _FENCE_LANGUAGES + r"[ \t]*$", re.IGNORECASE)
_FENCE_CLOSE_RE = re.compile(r"^```[ \t]*$")

# A simple heuristic: a "filename-like" line contains a dot or a path separator
# and is shorter than 200 chars.
_FILENAME_RE = re.compile(
    r"^[ \t]*"                   # optional leading whitespace
    r"(?:[A-Za-z]:[\\/])?"       # optional Windows drive letter
    r"[^\n\r`<>|?*\"]{1,200}"    # path body
    r"[A-Za-z0-9_\-]"            # must end with an identifier char (not a space/dot)
    r"[ \t]*$"
)


# ---------------------------------------------------------------------------
# 1.  parse_edits
# ---------------------------------------------------------------------------


def parse_edits(content: str) -> List[Tuple[str, str, str]]:
    """
    Parse an LLM response and return a list of ``(filename, search, replace)``
    tuples.

    Each tuple represents one SEARCH/REPLACE edit block.

    Parameters
    ----------
    content : str
        The raw text produced by the LLM.

    Returns
    -------
    list of (str, str, str)
        ``(filename, search_text, replace_text)`` tuples.
        ``search_text`` is empty for new-file creation.
        ``replace_text`` is empty for file deletion.
    """
    edits: List[Tuple[str, str, str]] = []

    lines = content.splitlines(keepends=True)
    i = 0
    n = len(lines)

    # Track the last "candidate filename" line we saw before an opening fence
    last_fname_line: str = ""

    while i < n:
        line = lines[i]
        stripped = line.rstrip("\n\r")

        # ----------------------------------------------------------------
        # Detect an opening fence
        # ----------------------------------------------------------------
        if _FENCE_OPEN_RE.match(stripped):
            fence_start = i

            # Collect lines inside the fence up to the matching close fence
            i += 1
            block_lines: List[str] = []
            while i < n:
                inner = lines[i].rstrip("\n\r")
                if _FENCE_CLOSE_RE.match(inner):
                    # Found closing fence
                    i += 1
                    break
                block_lines.append(lines[i])
                i += 1

            # Check whether this block contains SEARCH/REPLACE markers
            block_text = "".join(block_lines)
            if SEARCH_MARKER not in block_text or REPLACE_MARKER not in block_text:
                # Not an edit block — keep scanning
                last_fname_line = ""
                continue

            # ----------------------------------------------------------------
            # Split block into SEARCH and REPLACE sections
            # ----------------------------------------------------------------
            search_lines: List[str] = []
            replace_lines: List[str] = []
            section = "search"

            for bl in block_lines:
                bl_stripped = bl.rstrip("\n\r")
                if bl_stripped.rstrip() == SEARCH_MARKER:
                    section = "search"
                    continue
                if bl_stripped.rstrip() == DIVIDER_MARKER:
                    section = "replace"
                    continue
                if bl_stripped.rstrip() == REPLACE_MARKER:
                    section = "done"
                    continue
                if section == "search":
                    search_lines.append(bl)
                elif section == "replace":
                    replace_lines.append(bl)

            search_text = "".join(search_lines)
            replace_text = "".join(replace_lines)

            # ----------------------------------------------------------------
            # Determine the filename from the line(s) before the fence
            # ----------------------------------------------------------------
            fname = _extract_fname_before_fence(lines, fence_start, last_fname_line)
            if fname:
                edits.append((fname.strip(), search_text, replace_text))

            last_fname_line = ""
            continue

        # ----------------------------------------------------------------
        # Not a fence — remember this line as a possible filename candidate
        # ----------------------------------------------------------------
        stripped_no_backtick = stripped.strip()
        if stripped_no_backtick and not stripped_no_backtick.startswith("#"):
            last_fname_line = stripped_no_backtick
        else:
            last_fname_line = ""

        i += 1

    return edits


def _extract_fname_before_fence(
    lines: List[str],
    fence_index: int,
    last_candidate: str,
) -> Optional[str]:
    """
    Look at the lines immediately before `fence_index` to find a filename.

    We scan up to 3 lines above the fence.  A valid candidate is a line that
    looks like a file path (contains a '.' or path separator).

    Parameters
    ----------
    lines : list[str]
        All lines of the LLM response.
    fence_index : int
        Index of the opening fence line.
    last_candidate : str
        The last non-blank, non-comment line seen before this fence.

    Returns
    -------
    str or None
        The filename string, or ``None`` if nothing plausible was found.
    """
    # Search up to 3 lines back
    for look_back in range(1, min(4, fence_index + 1)):
        idx = fence_index - look_back
        candidate = lines[idx].rstrip("\n\r").strip()
        # Skip blank lines and pure markdown header lines
        if not candidate or candidate.startswith("#"):
            continue
        # Strip common markdown formatting that might wrap a filename
        candidate = candidate.strip("`").strip("*").strip()
        if _looks_like_filename(candidate):
            return candidate

    # Fall back to the last candidate seen in the scan loop
    if last_candidate and _looks_like_filename(last_candidate):
        return last_candidate

    return None


def _looks_like_filename(text: str) -> bool:
    """
    Heuristic: does *text* look like a file path?

    Accepts strings that contain a dot (extension) or a path separator.
    Rejects strings that are obviously prose.
    """
    text = text.strip()
    if not text:
        return False
    # Must not be too long
    if len(text) > 200:
        return False
    # Must contain a dot or slash/backslash
    if "." not in text and "/" not in text and "\\" not in text:
        return False
    # Must not contain spaces (filenames with spaces are rare in code projects)
    if " " in text and not (text.startswith('"') or text.startswith("'")):
        return False
    return True


# ---------------------------------------------------------------------------
# 2.  apply_edit
# ---------------------------------------------------------------------------


def apply_edit(fname: str, content: str, search: str, replace: str) -> str:
    """
    Apply a single SEARCH/REPLACE edit to `content` and return the new string.

    Parameters
    ----------
    fname : str
        File name (used only for error messages).
    content : str
        Current file content.
    search : str
        The exact text to locate in `content`.
    replace : str
        The text to substitute in place of `search`.

    Returns
    -------
    str
        The modified file content.

    Raises
    ------
    ValueError
        When the search string cannot be found using any matching strategy.
    """
    new_content, error = do_replace(fname, content, search, replace)
    if error:
        raise ValueError(
            f"Could not apply edit to {fname!r}:\n{error}\n"
            f"SEARCH block was:\n{search}"
        )
    return new_content  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# 3.  apply_edits
# ---------------------------------------------------------------------------


def apply_edits(
    edits: Sequence[Tuple[str, str, str]],
    io,
    dry_run: bool = False,
) -> List[str]:
    """
    Apply a list of ``(fname, search, replace)`` edits to files on disk.

    Parameters
    ----------
    edits : sequence of (str, str, str)
        Edit tuples as returned by :func:`parse_edits`.
    io : object
        ReviewForge IO object.  Must expose ``tool_error(msg)`` and
        ``read_text(path)`` / ``write_text(path, content)`` (or equivalent
        ``Path``-based operations are used as a fallback).
    dry_run : bool
        When ``True``, do not write any files.  Still returns the list of
        filenames that *would* be modified.

    Returns
    -------
    list[str]
        Filenames that were (or would be, in dry-run mode) modified.
    """
    modified: List[str] = []

    for fname, search, replace in edits:
        path = Path(fname)

        # ----------------------------------------------------------------
        # Read existing content
        # ----------------------------------------------------------------
        try:
            if hasattr(io, "read_text"):
                content = io.read_text(fname)
            else:
                content = path.read_text(encoding="utf-8") if path.exists() else ""
        except OSError:
            content = ""

        # ----------------------------------------------------------------
        # Apply the edit
        # ----------------------------------------------------------------
        new_content, error = do_replace(fname, content, search, replace)
        if error:
            if hasattr(io, "tool_error"):
                io.tool_error(
                    f"Edit failed for {fname!r}: {error}\n"
                    f"SEARCH block:\n{search}"
                )
            continue

        if new_content == content:
            # No change (e.g. replace == search); still count as "touched"
            pass

        modified.append(fname)

        # ----------------------------------------------------------------
        # Write back
        # ----------------------------------------------------------------
        if not dry_run:
            try:
                if hasattr(io, "write_text"):
                    io.write_text(fname, new_content)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(new_content, encoding="utf-8")
            except OSError as exc:
                if hasattr(io, "tool_error"):
                    io.tool_error(f"Could not write {fname!r}: {exc}")
                modified.pop()  # Didn't actually write it

    return modified


# ---------------------------------------------------------------------------
# 4.  do_replace  (multi-strategy replacement)
# ---------------------------------------------------------------------------


def do_replace(
    fname: str,
    content: str,
    search: str,
    replace: str,
    fence: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt to replace ``search`` with ``replace`` inside ``content``.

    Tries multiple matching strategies in order of increasing flexibility:

    1. **Exact string match** — fastest, most reliable.
    2. **Strip trailing whitespace** from each line before comparing.
    3. **Ignore leading whitespace** — re-indent the search block to match
       the indentation found in the file.
    4. **diff_match_patch fuzzy match** — last resort when ``diff_match_patch``
       is installed.

    Parameters
    ----------
    fname : str
        Filename (used in error messages only).
    content : str
        The current file content.
    search : str
        Text to locate.
    replace : str
        Replacement text.
    fence : str or None
        Unused (kept for API compatibility with future format variants).

    Returns
    -------
    (new_content, error_message)
        On success: ``(new_content, None)``.
        On failure: ``(None, descriptive_error_string)``.
    """
    # ----------------------------------------------------------------
    # Special case: empty search → create / overwrite entire file
    # ----------------------------------------------------------------
    if not search.strip():
        return replace, None

    # ----------------------------------------------------------------
    # Special case: empty replace → delete the search block
    # ----------------------------------------------------------------
    # (handled by normal replacement — replace is just an empty string)

    # ----------------------------------------------------------------
    # Strategy 1: Exact match
    # ----------------------------------------------------------------
    if search in content:
        return content.replace(search, replace, 1), None

    # ----------------------------------------------------------------
    # Strategy 2: Strip trailing whitespace from each line
    # ----------------------------------------------------------------
    result = _try_replace_strip_trailing(content, search, replace)
    if result is not None:
        return result, None

    # ----------------------------------------------------------------
    # Strategy 3: Flexible indentation matching
    # ----------------------------------------------------------------
    result = _try_replace_flexible_indent(content, search, replace)
    if result is not None:
        return result, None

    # ----------------------------------------------------------------
    # Strategy 4: diff_match_patch fuzzy match
    # ----------------------------------------------------------------
    if _HAS_DMP:
        result = _try_replace_dmp(content, search, replace)
        if result is not None:
            return result, None

    # ----------------------------------------------------------------
    # All strategies failed
    # ----------------------------------------------------------------
    return None, (
        f"The SEARCH block was not found in {fname!r}.\n"
        "Make sure the SEARCH text matches the file content exactly "
        "(including whitespace and indentation)."
    )


# ---------------------------------------------------------------------------
# Replacement strategy helpers
# ---------------------------------------------------------------------------


def _strip_trailing_lines(text: str) -> str:
    """Strip trailing whitespace from every line in *text*."""
    return "\n".join(line.rstrip() for line in text.splitlines())


def _try_replace_strip_trailing(
    content: str, search: str, replace: str
) -> Optional[str]:
    """
    Try replacement after stripping trailing whitespace from each line of
    both content and search.
    """
    content_stripped = _strip_trailing_lines(content)
    search_stripped = _strip_trailing_lines(search)

    if search_stripped not in content_stripped:
        return None

    # Find where the stripped search appears in the stripped content so we
    # can map back to the original content's character offsets.
    start = content_stripped.find(search_stripped)
    end = start + len(search_stripped)

    # Map stripped offsets → original offsets via line-by-line alignment
    orig_start, orig_end = _map_stripped_offsets_to_original(
        content, content_stripped, start, end
    )
    if orig_start is None or orig_end is None:
        return None

    return content[:orig_start] + replace + content[orig_end:]


def _map_stripped_offsets_to_original(
    original: str,
    stripped: str,
    start: int,
    end: int,
) -> Tuple[Optional[int], Optional[int]]:
    """
    Given character offsets into the *stripped* version of a text, return the
    corresponding offsets in the *original* text.

    This works by aligning original and stripped lines one-to-one.
    """
    orig_lines = original.splitlines(keepends=True)
    stripped_lines = stripped.splitlines(keepends=True)

    if len(orig_lines) != len(stripped_lines):
        return None, None

    # Build a mapping: stripped_char_pos → original_char_pos for line starts
    stripped_pos = 0
    orig_pos = 0
    orig_start = None
    orig_end = None

    for orig_line, stripped_line in zip(orig_lines, stripped_lines):
        if orig_start is None and stripped_pos + len(stripped_line) > start:
            # start falls inside this line
            char_offset_in_stripped_line = start - stripped_pos
            orig_start = orig_pos + min(
                char_offset_in_stripped_line, len(orig_line)
            )
        if orig_end is None and stripped_pos + len(stripped_line) >= end:
            char_offset_in_stripped_line = end - stripped_pos
            orig_end = orig_pos + min(
                char_offset_in_stripped_line, len(orig_line)
            )
            break
        stripped_pos += len(stripped_line)
        orig_pos += len(orig_line)

    # Handle edge case: end is exactly at the boundary of the last line
    if orig_end is None and stripped_pos == end:
        orig_end = orig_pos

    return orig_start, orig_end


def _common_leading_whitespace(lines: List[str]) -> str:
    """Return the longest common leading whitespace prefix shared by all non-empty lines."""
    non_empty = [ln for ln in lines if ln.strip()]
    if not non_empty:
        return ""
    prefix = non_empty[0]
    prefix = prefix[: len(prefix) - len(prefix.lstrip())]
    for line in non_empty[1:]:
        line_prefix = line[: len(line) - len(line.lstrip())]
        # Trim prefix to shortest common prefix
        while not line_prefix.startswith(prefix) and prefix:
            prefix = prefix[:-1]
    return prefix


def _try_replace_flexible_indent(
    content: str, search: str, replace: str
) -> Optional[str]:
    """
    Try to match the search block even when leading indentation differs.

    Strategy:
      - Strip the common leading whitespace from the SEARCH block.
      - Scan each position in the file where the first (de-indented) search
        line appears.
      - For each candidate position, check whether subsequent lines also match
        after de-indentation adjustment.
      - If found, re-indent the REPLACE block by the indentation detected in
        the file.
    """
    search_lines = search.splitlines(keepends=True)
    content_lines = content.splitlines(keepends=True)

    if not search_lines or not content_lines:
        return None

    search_indent = _common_leading_whitespace(search_lines)
    search_stripped_lines = [
        (ln[len(search_indent) :] if ln.startswith(search_indent) else ln)
        for ln in search_lines
    ]

    # The first non-empty search line (de-indented)
    first_key = next(
        (ln.rstrip("\n\r") for ln in search_stripped_lines if ln.strip()), None
    )
    if first_key is None:
        return None

    for ci, cline in enumerate(content_lines):
        c_stripped = cline.rstrip("\n\r")
        # Detect the indentation of this line in the file
        file_indent = c_stripped[: len(c_stripped) - len(c_stripped.lstrip())]
        c_stripped_no_indent = c_stripped.lstrip()

        if c_stripped_no_indent != first_key.lstrip():
            continue

        # Candidate match starting at ci — verify remaining lines
        matched = True
        for si, sline in enumerate(search_stripped_lines):
            actual_idx = ci + si
            if actual_idx >= len(content_lines):
                matched = False
                break
            actual_line = content_lines[actual_idx].rstrip("\n\r")
            expected_stripped = sline.rstrip("\n\r")
            # Compare without leading whitespace
            if actual_line.lstrip() != expected_stripped.lstrip():
                matched = False
                break

        if not matched:
            continue

        # ----------------------------------------------------------------
        # Found a match — reassemble
        # ----------------------------------------------------------------
        # Re-indent the replace block using the file's indentation at that spot
        replace_lines = replace.splitlines(keepends=True)
        replace_indent = _common_leading_whitespace(replace_lines)
        reindented_replace_lines = [
            (
                file_indent + ln[len(replace_indent):]
                if ln.startswith(replace_indent)
                else ln
            )
            for ln in replace_lines
        ]
        reindented_replace = "".join(reindented_replace_lines)

        # Build new content
        before = "".join(content_lines[:ci])
        after = "".join(content_lines[ci + len(search_stripped_lines):])
        return before + reindented_replace + after

    return None


def _try_replace_dmp(
    content: str, search: str, replace: str
) -> Optional[str]:
    """
    Use ``diff_match_patch`` for fuzzy/approximate matching as a last resort.

    We allow up to 10 % of the search length as edit distance and require the
    match score to exceed 0.5 (DMP convention).
    """
    if not _HAS_DMP:
        return None  # pragma: no cover

    dmp = _DiffMatchPatch()

    # Tune DMP for a reasonable fuzzy match
    dmp.Match_Threshold = 0.5   # similarity threshold (0=exact, 1=very fuzzy)
    dmp.Match_Distance = 1000   # characters around expected location to search

    # DMP works on plain text; we'll do a character-level patch
    # 1. Create a patch from search → replace
    patches = dmp.patch_make(search, replace)

    # 2. Apply the patch against the actual file content
    new_content, results = dmp.patch_apply(patches, content)

    if all(results):
        return new_content

    return None


# ---------------------------------------------------------------------------
# 5.  find_filename
# ---------------------------------------------------------------------------


def find_filename(
    lines: List[str],
    valid_fnames: Sequence[str],
    fence: Optional[str] = None,
) -> Optional[str]:
    """
    Given a list of lines preceding a code fence, return the most likely
    filename.

    Parameters
    ----------
    lines : list[str]
        Lines from the LLM response that appear before the opening fence.
        Typically the last few lines are most relevant.
    valid_fnames : sequence of str
        Collection of known filenames (e.g. files currently open in the
        coder's context).  Prefer a match from this list.
    fence : str or None
        The fence string (e.g. "```python").  Unused in this implementation
        but accepted for API extensibility.

    Returns
    -------
    str or None
        The best-match filename, or ``None`` if nothing plausible is found.
    """
    # Build a normalised set for fast membership testing
    valid_set = {_normalise_fname(f) for f in valid_fnames}
    valid_map = {_normalise_fname(f): f for f in valid_fnames}

    # Scan from most-recent line backwards
    candidates: List[str] = []
    for line in reversed(lines):
        stripped = line.strip().strip("`").strip("*").strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _looks_like_filename(stripped):
            candidates.append(stripped)

    for candidate in candidates:
        # Exact match against known filenames
        norm = _normalise_fname(candidate)
        if norm in valid_set:
            return valid_map[norm]

        # Partial match: known filename ends with the candidate's basename
        candidate_base = Path(candidate).name
        for vf in valid_fnames:
            if Path(vf).name == candidate_base:
                return vf

    # Return the first plausible candidate even if not in valid_fnames
    if candidates:
        return candidates[0]

    return None


def _normalise_fname(fname: str) -> str:
    """Normalise a filename for comparison (lowercase, forward slashes)."""
    return fname.strip().lower().replace("\\", "/")
