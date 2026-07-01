"""
reviewforge/onboarding.py

First-run setup wizard for ReviewForge.

Guides new users through:
  - Selecting a default LLM model from a curated list
  - Checking whether the required API key is already set
  - Optionally authenticating with OpenRouter for free/cheap access
"""

import os
from typing import Optional

# Re-export the OAuth helper so callers can import it from here
from reviewforge.openrouter import offer_openrouter_oauth  # noqa: F401

# ---------------------------------------------------------------------------
# Curated model list
# ---------------------------------------------------------------------------

SUGGESTED_MODELS = [
    ("gemini/gemini-2.0-flash",               "Google Gemini 2.0 Flash (FREE - Recommended)"),
    ("gpt-4o",                                 "OpenAI GPT-4o"),
    ("anthropic/claude-3-7-sonnet-20250219",   "Anthropic Claude 3.7 Sonnet"),
    ("deepseek/deepseek-chat",                 "DeepSeek Chat (Very cheap)"),
]

# ---------------------------------------------------------------------------
# API key environment variable mapping
# Each prefix maps to the env var that must be set for that provider.
# ---------------------------------------------------------------------------

_MODEL_ENV_MAP = [
    # (model_prefix, required_env_var)
    ("gemini/",     "GEMINI_API_KEY"),
    ("gpt-",        "OPENAI_API_KEY"),
    ("openai/",     "OPENAI_API_KEY"),
    ("anthropic/",  "ANTHROPIC_API_KEY"),
    ("claude",      "ANTHROPIC_API_KEY"),
    ("deepseek/",   "DEEPSEEK_API_KEY"),
    ("mistral/",    "MISTRAL_API_KEY"),
    ("cohere/",     "COHERE_API_KEY"),
    ("openrouter/", "OPENROUTER_API_KEY"),
]

# Fallback key used when none of the prefixes match
_FALLBACK_ENV_VAR = "OPENAI_API_KEY"


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def check_api_keys(model_name: str) -> bool:
    """
    Check whether the environment variable required for *model_name* is set.

    The function uses a prefix-based lookup table to resolve the model name
    to the appropriate env var.  For example:
      - 'gemini/gemini-2.0-flash' → GEMINI_API_KEY
      - 'gpt-4o'                  → OPENAI_API_KEY
      - 'anthropic/claude-…'      → ANTHROPIC_API_KEY

    Parameters
    ----------
    model_name : str
        The model identifier string (as passed to --model or similar).

    Returns
    -------
    bool
        True if the required env var is non-empty, False otherwise.
    """
    lower = model_name.lower()
    for prefix, env_var in _MODEL_ENV_MAP:
        if lower.startswith(prefix.lower()):
            return bool(os.environ.get(env_var, "").strip())
    # Unknown provider — check the generic fallback
    return bool(os.environ.get(_FALLBACK_ENV_VAR, "").strip())


def _required_env_var(model_name: str) -> str:
    """Return the env var name needed for *model_name* (for display purposes)."""
    lower = model_name.lower()
    for prefix, env_var in _MODEL_ENV_MAP:
        if lower.startswith(prefix.lower()):
            return env_var
    return _FALLBACK_ENV_VAR


def select_default_model(io, args) -> Optional[str]:
    """
    Interactive first-run wizard that helps the user pick a default model.

    Called when no ``--model`` flag was provided AND no recognised API key
    is found in the environment.  The function:

    1. Displays the ``SUGGESTED_MODELS`` list with indices.
    2. Asks the user to pick one (defaulting to 0 = Gemini Flash).
    3. Checks whether the required API key is already in the environment.
    4. If not, offers to open OpenRouter OAuth (free tier) OR prompts the
       user to set the key manually.
    5. Returns the chosen model name, or None if the user aborts.

    Parameters
    ----------
    io   : reviewforge IO object
        Must expose ``tool_output(msg)``, ``tool_warning(msg)``,
        ``prompt(message, default='') -> str``, and
        ``confirm(question) -> bool``.
    args : argparse.Namespace
        The parsed CLI args.  ``args.model`` is checked to skip the wizard
        when the user already supplied a model.

    Returns
    -------
    str | None
        The model name selected (or already set), or None if the user quit.
    """
    # If a model was already chosen via CLI, honour it without interruption
    existing_model = getattr(args, "model", None)
    if existing_model:
        return existing_model

    io.tool_output(
        "\n[ReviewForge] Welcome! Let's pick a model to get started.\n"
    )

    # Display numbered list
    for i, (model_id, description) in enumerate(SUGGESTED_MODELS):
        io.tool_output(f"  [{i}] {description}")
        io.tool_output(f"      ({model_id})")

    io.tool_output("")

    # Prompt for selection
    try:
        raw = io.prompt(
            f"Enter number [0-{len(SUGGESTED_MODELS) - 1}] "
            f"(default 0 — Gemini Flash): ",
            default="0",
        ).strip()
    except (EOFError, KeyboardInterrupt):
        io.tool_warning("Model selection cancelled.")
        return None

    # Parse input
    try:
        choice = int(raw)
        if not (0 <= choice < len(SUGGESTED_MODELS)):
            raise ValueError
    except ValueError:
        io.tool_warning(
            f"Invalid choice '{raw}', defaulting to Gemini 2.0 Flash."
        )
        choice = 0

    model_name, description = SUGGESTED_MODELS[choice]
    io.tool_output(f"\nSelected: {description}\n")

    # Check if the key is already present
    if check_api_keys(model_name):
        io.tool_output(
            f"  API key found for {model_name} — you're all set!"
        )
        return model_name

    # Key missing — offer options
    env_var = _required_env_var(model_name)
    io.tool_warning(
        f"  Required environment variable '{env_var}' is not set."
    )

    # For the Gemini free tier, suggest setting the key from AI Studio
    if model_name.startswith("gemini/"):
        io.tool_output(
            "  Get a free Gemini API key at: https://aistudio.google.com/apikey"
        )

    # Offer OpenRouter as a fallback (it hosts most models under one key)
    try:
        use_openrouter = io.confirm(
            "Would you like to use OpenRouter instead "
            "(provides free access to many models)?"
        )
    except (EOFError, KeyboardInterrupt):
        use_openrouter = False

    if use_openrouter:
        api_key = offer_openrouter_oauth(io)
        if api_key:
            os.environ["OPENROUTER_API_KEY"] = api_key
            # Switch to the OpenRouter-compatible model ID
            or_model = f"openrouter/{model_name}"
            io.tool_output(
                f"  OpenRouter key set.  Using model: {or_model}"
            )
            return or_model

    # Fall through: ask the user to set the key manually
    io.tool_output(
        f"\n  To set the key now, run:\n"
        f"    export {env_var}=<your-api-key>    (Linux / macOS)\n"
        f"    setx {env_var} <your-api-key>       (Windows)\n"
        f"\n  Then restart ReviewForge.  Proceeding anyway…"
    )
    return model_name
