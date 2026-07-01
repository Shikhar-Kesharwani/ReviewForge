"""
reviewforge/exceptions.py

Custom exception types for ReviewForge.

Classes
-------
ReviewForgeException
    Base class for all ReviewForge-specific exceptions.

LiteLLMExceptions
    Utility class that maps common LiteLLM / provider API errors to simple
    category strings so the rest of the codebase can handle them uniformly.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Base exception
# ---------------------------------------------------------------------------

class ReviewForgeException(Exception):
    """
    Base class for all ReviewForge exceptions.

    Catch this type to handle any error raised intentionally by ReviewForge
    without needing to import every subclass.
    """


# ---------------------------------------------------------------------------
# LiteLLM / provider error classifier
# ---------------------------------------------------------------------------

class LiteLLMExceptions:
    """
    Detects and categorises common LiteLLM / provider API errors.

    The class holds a mapping from exception *category* to a list of
    substring patterns that appear in the exception type name or message.
    Call ``match(ex)`` to get the category string for a given exception,
    or ``None`` if it does not belong to a known category.

    Categories
    ----------
    'ratelimit'
        The provider rate-limited the request (HTTP 429).
    'context'
        The prompt or completion exceeded the model's context window.
    'invalid'
        The request was malformed or contained an unsupported parameter.
    'permission'
        Authentication failed or the API key lacks the required permissions.
    'connection'
        A network-level error prevented the request from reaching the API.

    Usage
    -----
    >>> lite_ex = LiteLLMExceptions()
    >>> category = lite_ex.match(some_exception)
    >>> if category == 'ratelimit':
    ...     time.sleep(60)
    """

    # Each entry maps a category name to patterns that may appear in the
    # fully-qualified exception class name OR in the string of the exception.
    # Patterns are matched case-insensitively.
    _PATTERNS: dict[str, list[str]] = {
        "ratelimit": [
            "ratelimit",
            "rate_limit",
            "rateerror",
            "toomanyrequests",
            "429",
        ],
        "context": [
            "contextwindow",
            "context_window",
            "context_length",
            "contextlength",
            "tokenslimit",
            "tokens_limit",
            "maximum context",
            "max_tokens",
            "prompt is too long",
            "too many tokens",
            "input is too long",
        ],
        "invalid": [
            "invalidrequest",
            "invalid_request",
            "badrequesterror",
            "bad_request",
            "invalidargument",
            "invalid_argument",
            "400",
        ],
        "permission": [
            "authenticationerror",
            "authentication_error",
            "permissiondenied",
            "permission_denied",
            "unauthorised",
            "unauthorized",
            "forbidden",
            "apikey",
            "api_key",
            "401",
            "403",
        ],
        "connection": [
            "connectionerror",
            "connection_error",
            "timeout",
            "serviceunavailable",
            "service_unavailable",
            "apierror",
            "networkerror",
            "network_error",
            "503",
            "502",
        ],
    }

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def match(self, ex: BaseException) -> str | None:
        """
        Return the category string for *ex*, or ``None`` if unknown.

        The method checks both the fully-qualified class name of the
        exception and its string representation against the pattern lists.

        Parameters
        ----------
        ex:
            Any exception instance to classify.

        Returns
        -------
        str or None
            One of ``'ratelimit'``, ``'context'``, ``'invalid'``,
            ``'permission'``, ``'connection'``, or ``None``.
        """
        # Build a single lowercase search string from type name + message
        type_name = type(ex).__name__.lower()
        # Also include the fully-qualified module path when available
        module = getattr(type(ex), "__module__", "") or ""
        full_type = f"{module}.{type_name}".lower()
        message = str(ex).lower()
        haystack = f"{full_type} {message}"

        for category, patterns in self._PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in haystack:
                    return category

        return None

    def is_ratelimit(self, ex: BaseException) -> bool:
        """Return True if *ex* is a rate-limit error."""
        return self.match(ex) == "ratelimit"

    def is_context(self, ex: BaseException) -> bool:
        """Return True if *ex* signals a context-window overflow."""
        return self.match(ex) == "context"

    def is_invalid(self, ex: BaseException) -> bool:
        """Return True if *ex* is an invalid-request error."""
        return self.match(ex) == "invalid"

    def is_permission(self, ex: BaseException) -> bool:
        """Return True if *ex* is an authentication / permission error."""
        return self.match(ex) == "permission"

    def is_connection(self, ex: BaseException) -> bool:
        """Return True if *ex* is a network / connection error."""
        return self.match(ex) == "connection"
