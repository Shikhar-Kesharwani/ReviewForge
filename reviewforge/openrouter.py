"""
reviewforge/openrouter.py

OpenRouter OAuth integration for ReviewForge.

OpenRouter (https://openrouter.ai) provides a unified API gateway for many
LLM providers, often with free or very cheap access tiers.  This module lets
users authenticate via OAuth and retrieve their API key without leaving the
terminal.
"""

import webbrowser
from typing import List, Optional

import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

OPENROUTER_AUTH_URL = "https://openrouter.ai/auth"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"

# Timeout (seconds) for requests to the OpenRouter API
_REQUEST_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def offer_openrouter_oauth(io) -> Optional[str]:
    """
    Interactively offer the user an OpenRouter OAuth login flow.

    The flow works as follows:
    1. Ask the user if they want to authenticate with OpenRouter.
    2. If yes, open the browser at ``OPENROUTER_AUTH_URL``.
    3. Instruct the user to complete the sign-in and copy their API key.
    4. Prompt the user to paste the key back into the terminal.
    5. Return the key (stripped of whitespace), or None if the user skips.

    Parameters
    ----------
    io : reviewforge IO object
        Must expose:
          - ``confirm(question) -> bool``
          - ``prompt(message, default='') -> str``
          - ``tool_output(msg)``
          - ``tool_warning(msg)``

    Returns
    -------
    str | None
        The OpenRouter API key entered by the user, or None if they declined
        or provided an empty string.
    """
    try:
        wants_auth = io.confirm(
            "Would you like to authenticate with OpenRouter for free/cheap "
            "model access?"
        )
    except (EOFError, KeyboardInterrupt):
        return None

    if not wants_auth:
        return None

    io.tool_output(
        "\nOpening your browser to OpenRouter authentication…\n"
        "  1. Sign in with your preferred provider.\n"
        "  2. Copy the API key shown on the page.\n"
        "  3. Paste it here when prompted.\n"
    )

    try:
        webbrowser.open(OPENROUTER_AUTH_URL)
    except Exception:
        io.tool_warning(
            f"Could not open browser automatically. "
            f"Please visit: {OPENROUTER_AUTH_URL}"
        )

    try:
        api_key = io.prompt("Paste your OpenRouter API key here: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not api_key:
        io.tool_warning("No API key provided — OpenRouter auth skipped.")
        return None

    io.tool_output("OpenRouter API key saved successfully.")
    return api_key


def get_openrouter_models() -> List[str]:
    """
    Fetch the list of model IDs available through OpenRouter.

    Makes a single GET request to the OpenRouter models endpoint and returns
    a sorted list of model ID strings.

    Returns
    -------
    list[str]
        A (possibly empty) list of model ID strings such as
        ``["openai/gpt-4o", "anthropic/claude-3-haiku", ...]``.
        Returns an empty list on any network or parse failure.
    """
    try:
        resp = requests.get(OPENROUTER_MODELS_URL, timeout=_REQUEST_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()

        # The response shape is {"data": [{"id": "...", ...}, ...]}
        data = payload.get("data", [])
        model_ids = [
            entry["id"]
            for entry in data
            if isinstance(entry, dict) and "id" in entry
        ]
        return sorted(model_ids)

    except requests.exceptions.RequestException:
        # Network error, timeout, non-2xx status — fail silently
        return []
    except (KeyError, ValueError, TypeError):
        # Unexpected response shape — fail silently
        return []
