"""
reviewforge/versioncheck.py

Checks PyPI for the latest published version of the reviewforge package and
notifies the user when an upgrade is available.  Responses are cached for 24
hours in ~/.reviewforge/version_cache.json to keep network traffic minimal.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PYPI_URL = "https://pypi.org/pypi/reviewforge/json"
CACHE_DIR = Path.home() / ".reviewforge"
CACHE_FILE = CACHE_DIR / "version_cache.json"
CACHE_TTL_SECONDS = 86_400  # 24 hours

GITHUB_MAIN_BRANCH_URL = (
    "git+https://github.com/Shikhar/reviewforge.git"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_local_version() -> str:
    """Return the currently installed reviewforge version string."""
    try:
        from reviewforge import __version__
        return __version__
    except ImportError:
        return "0.0.0"


def _read_cache() -> Optional[dict]:
    """
    Load the version cache from disk.

    Returns the parsed JSON dict if the file exists and is not stale, or
    None if the cache is missing / expired / unreadable.
    """
    if not CACHE_FILE.exists():
        return None
    try:
        with CACHE_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        cached_at = data.get("cached_at", 0)
        if time.time() - cached_at > CACHE_TTL_SECONDS:
            return None  # expired
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(latest_version: str) -> None:
    """Persist the latest version string alongside a timestamp."""
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "latest_version": latest_version,
            "cached_at": time.time(),
        }
        with CACHE_FILE.open("w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
    except OSError:
        pass  # non-fatal; we just skip caching


def _fetch_latest_from_pypi() -> Optional[str]:
    """
    Query PyPI for the latest published version of reviewforge.

    Returns the version string on success, or None if the request fails.
    """
    try:
        resp = requests.get(PYPI_URL, timeout=5)
        resp.raise_for_status()
        payload = resp.json()
        return payload["info"]["version"]
    except Exception:
        return None


def _parse_version(version_str: str):
    """
    Convert a version string like '1.2.3' into a comparable tuple of ints.

    Supports plain semver strings; non-numeric components are treated as 0.
    """
    parts = []
    for part in version_str.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    return tuple(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_version(io, verbose: bool = False) -> None:
    """
    Check PyPI for a newer version of reviewforge.

    The check uses a 24-hour disk cache so that it does not hammer PyPI on
    every invocation.  If a newer version is found, a warning is printed
    through *io*.

    Parameters
    ----------
    io      : reviewforge IO object
        Must expose ``tool_warning(msg)`` and optionally ``tool_output(msg)``.
    verbose : bool
        When True, print a message even if the package is up-to-date.
    """
    local_version = _get_local_version()

    # Try the cache first
    cached = _read_cache()
    if cached:
        latest_version = cached.get("latest_version", local_version)
        source = "cache"
    else:
        latest_version = _fetch_latest_from_pypi()
        if latest_version is None:
            if verbose:
                io.tool_output(
                    "reviewforge: Could not reach PyPI to check for updates."
                )
            return
        _write_cache(latest_version)
        source = "PyPI"

    if verbose:
        io.tool_output(
            f"reviewforge: local={local_version}  latest={latest_version}"
            f"  (source: {source})"
        )

    if _parse_version(latest_version) > _parse_version(local_version):
        io.tool_warning(
            f"A newer version of reviewforge is available: {latest_version} "
            f"(you have {local_version}).\n"
            "  Run: pip install --upgrade reviewforge\n"
            "  Or inside ReviewForge: /upgrade"
        )


def install_upgrade(io) -> None:
    """
    Upgrade reviewforge via pip in the current Python environment.

    Runs ``pip install --upgrade reviewforge`` as a subprocess and streams
    the output through *io*.

    Parameters
    ----------
    io : reviewforge IO object
        Must expose ``tool_output(msg)`` and ``tool_error(msg)``.
    """
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "reviewforge"]
    io.tool_output(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            io.tool_output(result.stdout.strip())
        if result.returncode == 0:
            io.tool_output("reviewforge upgraded successfully.")
        else:
            io.tool_error(
                f"pip exited with code {result.returncode}.\n"
                + (result.stderr.strip() or "")
            )
    except FileNotFoundError:
        io.tool_error("pip not found. Please upgrade reviewforge manually.")
    except Exception as exc:
        io.tool_error(f"Upgrade failed: {exc}")


def install_from_main_branch(io) -> None:
    """
    Install the bleeding-edge version of reviewforge directly from the main
    branch on GitHub via pip.

    Useful for testing unreleased features or fixes before they hit PyPI.

    Parameters
    ----------
    io : reviewforge IO object
        Must expose ``tool_output(msg)`` and ``tool_error(msg)``.
    """
    cmd = [
        sys.executable, "-m", "pip", "install",
        GITHUB_MAIN_BRANCH_URL,
    ]
    io.tool_output(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            io.tool_output(result.stdout.strip())
        if result.returncode == 0:
            io.tool_output(
                "reviewforge installed from main branch successfully."
            )
        else:
            io.tool_error(
                f"pip exited with code {result.returncode}.\n"
                + (result.stderr.strip() or "")
            )
    except FileNotFoundError:
        io.tool_error("pip not found. Please install from main manually.")
    except Exception as exc:
        io.tool_error(f"Install from main branch failed: {exc}")
