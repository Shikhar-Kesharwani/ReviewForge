"""
reviewforge/llm.py
~~~~~~~~~~~~~~~~~~
LiteLLM initialization module for ReviewForge.

Configures litellm on import and exposes a backoff-powered retry
decorator that callers can apply to functions that hit LLM endpoints.

Usage
-----
    from reviewforge.llm import litellm, retry_on_transient_error

    @retry_on_transient_error()
    def call_model(...):
        return litellm.completion(...)
"""

from __future__ import annotations

import logging
from typing import Callable, Tuple, Type

import backoff
import litellm

# ---------------------------------------------------------------------------
# Global litellm configuration
# ---------------------------------------------------------------------------

# Suppress the startup banner and verbose debug lines that litellm prints by
# default; ReviewForge controls its own logging.
litellm.suppress_debug_info = True

# When a provider does not support a particular parameter (e.g. `top_p` for
# some Gemini endpoints) litellm will silently drop it instead of raising an
# error, so the call can succeed with a best-effort set of parameters.
litellm.drop_params = True

# Silence litellm's own logger to prevent double-logging in ReviewForge's
# output; the application logger will surface any errors we care about.
logging.getLogger("litellm").setLevel(logging.WARNING)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)

# ---------------------------------------------------------------------------
# Transient error types that are worth retrying
# ---------------------------------------------------------------------------

#: Exceptions that indicate a temporary upstream problem (rate-limit, network
#: blip, etc.) and should trigger an automatic retry with back-off.
_TRANSIENT_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    litellm.exceptions.RateLimitError,
    litellm.exceptions.ServiceUnavailableError,
    litellm.exceptions.APIConnectionError,
    litellm.exceptions.Timeout,
    litellm.exceptions.APIError,
)


def _is_transient(exc: Exception) -> bool:
    """Return *True* when *exc* is a transient error worth retrying."""
    return isinstance(exc, _TRANSIENT_EXCEPTIONS)


# ---------------------------------------------------------------------------
# Public retry decorator factory
# ---------------------------------------------------------------------------

def retry_on_transient_error(
    max_tries: int = 5,
    max_time: float = 120.0,
    base: float = 2.0,
    factor: float = 1.0,
    jitter: bool = True,
) -> Callable:
    """Return a *backoff* decorator configured for LLM transient errors.

    Parameters
    ----------
    max_tries:
        Maximum number of attempts (including the first one).
    max_time:
        Give up after this many seconds of total elapsed time, regardless
        of how many tries remain.
    base:
        Exponential-back-off base (default 2 -> 1 s, 2 s, 4 s, ...).
    factor:
        Multiplier applied to each back-off interval.
    jitter:
        If *True* (default), add a small random jitter to each interval so
        that concurrent callers don't all retry at the same moment.

    Returns
    -------
    Callable
        A decorator that can be applied to any function that calls litellm.

    Example
    -------
    ::

        @retry_on_transient_error(max_tries=3)
        def my_llm_call(model, messages):
            return litellm.completion(model=model, messages=messages)
    """
    _jitter_fn = backoff.full_jitter if jitter else None

    def decorator(func: Callable) -> Callable:
        wrapped = backoff.on_exception(
            backoff.expo,
            _TRANSIENT_EXCEPTIONS,
            max_tries=max_tries,
            max_time=max_time,
            base=base,
            factor=factor,
            jitter=_jitter_fn,
            giveup=lambda exc: not _is_transient(exc),
        )(func)
        return wrapped

    return decorator


# ---------------------------------------------------------------------------
# Re-export litellm so callers can write:
#   from reviewforge.llm import litellm
# and be guaranteed that the configuration above has been applied.
# ---------------------------------------------------------------------------

__all__ = [
    "litellm",
    "retry_on_transient_error",
    "_TRANSIENT_EXCEPTIONS",
    "_is_transient",
]
