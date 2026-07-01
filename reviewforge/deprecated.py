"""
reviewforge/deprecated.py

Handles deprecated CLI arguments and provides backward-compatible model shortcuts.
When a user passes an old flag like --gpt4, this module converts it to the
modern --model equivalent and prints a deprecation warning.
"""

import argparse


# ---------------------------------------------------------------------------
# Registry of deprecated model shortcut flags
# Each entry is a tuple of (old_flag, new_flag_value, display_model_name)
# old_flag      : the argparse dest name (without '--'), e.g. 'gpt4'
# new_flag_value: the string to pass to --model
# display_model_name: human-readable label used in the warning message
# ---------------------------------------------------------------------------
DEPRECATED_MODEL_ARGS = [
    # OpenAI
    ("gpt4",         "gpt-4",                    "GPT-4"),
    ("gpt4o",        "gpt-4o",                   "GPT-4o"),
    ("gpt35turbo",   "gpt-3.5-turbo",            "GPT-3.5 Turbo"),
    ("gpt4turbo",    "gpt-4-turbo",              "GPT-4 Turbo"),
    # Anthropic
    ("claude",       "claude-3-opus-20240229",   "Claude 3 Opus"),
    ("claude3",      "claude-3-opus-20240229",   "Claude 3 Opus"),
    ("claude3sonnet","claude-3-sonnet-20240229", "Claude 3 Sonnet"),
    ("claude3haiku", "claude-3-haiku-20240307",  "Claude 3 Haiku"),
    # Google
    ("gemini",       "gemini/gemini-2.0-flash",  "Gemini 2.0 Flash"),
    ("gemini15pro",  "gemini/gemini-1.5-pro",    "Gemini 1.5 Pro"),
    ("gemini15flash","gemini/gemini-1.5-flash",  "Gemini 1.5 Flash"),
    # Mistral / open-source
    ("mixtral",      "mistral/mixtral-8x7b-instruct", "Mixtral 8x7B"),
    ("deepseek",     "deepseek/deepseek-chat",   "DeepSeek Chat"),
]


def add_deprecated_model_args(parser: argparse.ArgumentParser) -> None:
    """
    Register all deprecated shortcut flags on *parser*.

    Each flag is hidden from --help output (help=argparse.SUPPRESS) so that
    it does not clutter the user-facing interface, but still parses correctly
    so we can detect its use and emit a meaningful deprecation warning.

    Parameters
    ----------
    parser : argparse.ArgumentParser
        The top-level argument parser for the ReviewForge CLI.
    """
    for old_flag, _new_value, _display_name in DEPRECATED_MODEL_ARGS:
        cli_flag = f"--{old_flag}"
        parser.add_argument(
            cli_flag,
            dest=old_flag,
            action="store_true",
            default=False,
            help=argparse.SUPPRESS,  # hidden from help text
        )


def handle_deprecated_model_args(args: argparse.Namespace, io) -> argparse.Namespace:
    """
    Inspect *args* for any deprecated model-shortcut flags.

    If one is detected:
      1. A deprecation warning is printed via ``io.tool_warning()``.
      2. ``args.model`` is set to the equivalent modern model string (unless
         the user has already explicitly provided ``--model``).

    If the user has both a deprecated flag and ``--model``, the explicit
    ``--model`` value wins and a warning is still shown.

    Parameters
    ----------
    args : argparse.Namespace
        Parsed arguments from ArgumentParser.parse_args().
    io   : reviewforge IO object
        Must expose a ``tool_warning(message: str)`` method.

    Returns
    -------
    argparse.Namespace
        The (possibly mutated) args namespace.
    """
    for old_flag, new_value, display_name in DEPRECATED_MODEL_ARGS:
        flag_active = getattr(args, old_flag, False)
        if not flag_active:
            continue

        # Build the deprecation warning text
        cli_flag = f"--{old_flag}"
        warning = (
            f"The '{cli_flag}' flag is deprecated and will be removed in a "
            f"future release.\n"
            f"  Please use '--model {new_value}' instead."
        )
        io.tool_warning(warning)

        # Only override --model when the user has NOT explicitly set it
        existing_model = getattr(args, "model", None)
        if existing_model is None:
            args.model = new_value
        else:
            # The explicit --model takes precedence; just notify the user
            io.tool_warning(
                f"  '{cli_flag}' was ignored because '--model {existing_model}' "
                f"was also provided."
            )

        # We process only the first deprecated flag encountered to avoid
        # confusing double-assignment if someone passes two flags by mistake.
        break

    return args
