"""
reviewforge/models.py
~~~~~~~~~~~~~~~~~~~~~
Model abstraction layer for ReviewForge.

This module defines:

- ``DEFAULT_MODEL_NAME``  -- the default LLM to use when none is specified.
- ``MODEL_ALIASES``       -- short friendly names mapped to full model strings.
- ``ModelSettings``       -- a dataclass holding per-model behavioural config.
- ``KNOWN_MODELS``        -- a registry of pre-configured ``ModelSettings``.
- ``Model``               -- high-level model wrapper used throughout the app.
- ``sanity_check_models`` -- warns about missing / unknown models on startup.
- ``register_models``     -- loads extra ``ModelSettings`` from a YAML file.
- ``get_model_info``      -- safely retrieves LiteLLM metadata for a model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional

import yaml

from reviewforge.llm import litellm
from reviewforge import sendchat

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default model
# ---------------------------------------------------------------------------

#: The model used when the caller does not specify one.
DEFAULT_MODEL_NAME: str = "gemini/gemini-2.0-flash"

# ---------------------------------------------------------------------------
# Alias table
# ---------------------------------------------------------------------------

#: Short, memorable names mapped to canonical LiteLLM model strings.
MODEL_ALIASES: Dict[str, str] = {
    "flash":   "gemini/gemini-2.0-flash",
    "flash-lite": "gemini/gemini-2.0-flash-lite",
    "pro":     "gemini/gemini-1.5-pro",
    "gemini":  "gemini/gemini-2.0-flash",
    "gpt4o":   "gpt-4o",
    "gpt4":    "gpt-4-turbo",
    "sonnet":  "anthropic/claude-3-7-sonnet-20250219",
    "haiku":   "anthropic/claude-3-5-haiku-20241022",
    "opus":    "anthropic/claude-3-opus-20240229",
    "deepseek": "deepseek/deepseek-chat",
    "r1":      "deepseek/deepseek-reasoner",
    "o1":      "o1",
    "o3-mini": "o3-mini",
}


def _resolve_alias(name: str) -> str:
    """Return the canonical model string for *name*, resolving aliases."""
    return MODEL_ALIASES.get(name, name)


# ---------------------------------------------------------------------------
# ModelSettings dataclass
# ---------------------------------------------------------------------------

@dataclass
class ModelSettings:
    """Per-model behavioural configuration for ReviewForge.

    All fields have sensible defaults so only the fields that differ from the
    defaults need to be specified when constructing a ``ModelSettings`` entry.

    Attributes
    ----------
    name:
        The canonical LiteLLM model string (e.g. ``"gemini/gemini-2.0-flash"``).
    edit_format:
        The diff/patch format used when the model proposes code edits.
        Supported values: ``"diff"``, ``"whole"``, ``"udiff"``.
    weak_model_name:
        Canonical name of a cheaper/faster model to use for lightweight tasks
        such as commit-message generation.  *None* means use the main model.
    editor_model_name:
        Canonical name of a model that performs the actual file-editing step
        in a two-model workflow.  *None* means the same model does both.
    editor_edit_format:
        Edit format override for the editor model.  *None* inherits
        ``edit_format``.
    use_repo_map:
        Whether to include a repository map in the system prompt.
    send_undo_reply:
        Whether ReviewForge should send a follow-up reply after the user
        undoes an edit.
    lazy:
        When *True* the model tends to emit abbreviated / lazy completions;
        ReviewForge adds extra instructions to counter this.
    reminder:
        Where to inject the system-prompt reminder in long conversations.
        ``"user"`` prepends it to the next user message; ``"system"``
        re-sends it as a system message.
    examples_as_sys_msg:
        Send few-shot examples inside the system message rather than as
        early user/assistant turns.
    cache_control:
        Enable prompt-caching hints (Anthropic feature).
    streaming:
        Whether to use streaming completions by default.
    max_tokens:
        Hard cap on the number of tokens in the completion.  *None* means use
        the provider default.
    use_temperature:
        Default sampling temperature.  0 = greedy.
    reasoning_tag:
        Some models (e.g. DeepSeek-R1) emit ``<think>…</think>`` blocks.
        Setting this to ``"think"`` tells ReviewForge to strip / handle them.
    use_system_prompt:
        Whether to include a ``system`` role message.  Some older / constrained
        APIs do not support it.
    """

    name: str
    edit_format: str = "diff"
    weak_model_name: Optional[str] = None
    editor_model_name: Optional[str] = None
    editor_edit_format: Optional[str] = None
    use_repo_map: bool = True
    send_undo_reply: bool = True
    lazy: bool = False
    reminder: str = "user"
    examples_as_sys_msg: bool = False
    cache_control: bool = False
    streaming: bool = True
    max_tokens: Optional[int] = None
    use_temperature: float = 0
    reasoning_tag: Optional[str] = None
    use_system_prompt: bool = True


# ---------------------------------------------------------------------------
# Built-in model registry
# ---------------------------------------------------------------------------

#: Pre-configured ``ModelSettings`` for well-known models.
KNOWN_MODELS: List[ModelSettings] = [
    ModelSettings(
        name="gemini/gemini-2.0-flash",
        edit_format="diff",
        use_repo_map=True,
        streaming=True,
    ),
    ModelSettings(
        name="gemini/gemini-2.0-flash-lite",
        edit_format="diff",
        use_repo_map=True,
        streaming=True,
    ),
    ModelSettings(
        name="gemini/gemini-1.5-pro",
        edit_format="diff",
        use_repo_map=True,
        streaming=True,
    ),
    ModelSettings(
        name="gpt-4o",
        edit_format="diff",
        use_repo_map=True,
        streaming=True,
    ),
    ModelSettings(
        name="gpt-4-turbo",
        edit_format="diff",
        use_repo_map=True,
        streaming=True,
    ),
    ModelSettings(
        name="anthropic/claude-3-7-sonnet-20250219",
        edit_format="diff",
        use_repo_map=True,
        cache_control=True,
        streaming=True,
    ),
    ModelSettings(
        name="anthropic/claude-3-5-haiku-20241022",
        edit_format="diff",
        use_repo_map=True,
        cache_control=True,
        streaming=True,
    ),
    ModelSettings(
        name="anthropic/claude-3-opus-20240229",
        edit_format="diff",
        use_repo_map=True,
        cache_control=True,
        streaming=True,
    ),
    ModelSettings(
        name="deepseek/deepseek-chat",
        edit_format="diff",
        use_repo_map=True,
        streaming=True,
    ),
    ModelSettings(
        name="deepseek/deepseek-reasoner",
        edit_format="diff",
        use_repo_map=True,
        reasoning_tag="think",
        streaming=True,
    ),
    ModelSettings(
        name="o1",
        edit_format="diff",
        use_repo_map=True,
        use_temperature=1,   # o-series models only accept temperature=1
        use_system_prompt=False,
        streaming=False,
    ),
    ModelSettings(
        name="o3-mini",
        edit_format="diff",
        use_repo_map=True,
        use_temperature=1,
        use_system_prompt=False,
        streaming=False,
    ),
]

# Internal lookup: canonical name -> ModelSettings
_KNOWN_MODELS_BY_NAME: Dict[str, ModelSettings] = {
    ms.name: ms for ms in KNOWN_MODELS
}


# ---------------------------------------------------------------------------
# get_model_info helper
# ---------------------------------------------------------------------------

def get_model_info(model_name: str) -> Dict[str, Any]:
    """Safely retrieve LiteLLM cost / capability metadata for *model_name*.

    Parameters
    ----------
    model_name:
        Canonical LiteLLM model string.

    Returns
    -------
    dict
        A dict with keys such as ``max_tokens``, ``max_input_tokens``,
        ``input_cost_per_token``, etc., or an empty dict when no metadata is
        available (unknown model, network error, etc.).
    """
    try:
        info = litellm.get_model_info(model_name)
        return info if isinstance(info, dict) else {}
    except Exception as exc:
        logger.debug("get_model_info(%r) failed: %s", model_name, exc)
        return {}


# ---------------------------------------------------------------------------
# Model class
# ---------------------------------------------------------------------------

class Model:
    """High-level model wrapper used throughout ReviewForge.

    ``Model`` resolves aliases, applies ``ModelSettings`` from
    :data:`KNOWN_MODELS`, and provides helper methods for token counting,
    message sending, and accessing LiteLLM metadata.

    Parameters
    ----------
    model_name:
        A canonical model string **or** a short alias from
        :data:`MODEL_ALIASES`.
    weak_model:
        An existing ``Model`` instance to use as the weak model.  When
        *None* (default) ReviewForge instantiates one from
        ``settings.weak_model_name`` (if set).
    editor_model:
        An existing ``Model`` instance to use as the editor model.  When
        *None* (default) ReviewForge instantiates one from
        ``settings.editor_model_name`` (if set).

    Attributes
    ----------
    _name : str
        The resolved canonical model string.
    settings : ModelSettings
        Merged settings (KNOWN_MODELS entry or defaults).
    weak_model : Model | None
        The weak / cheap helper model.
    editor_model : Model | None
        The editor model (two-model workflow).
    """

    def __init__(
        self,
        model_name: str,
        weak_model: Optional["Model"] = None,
        editor_model: Optional["Model"] = None,
    ) -> None:
        # Resolve alias first.
        self._name: str = _resolve_alias(model_name)

        # Apply known settings or fall back to defaults.
        self.settings: ModelSettings = _KNOWN_MODELS_BY_NAME.get(
            self._name,
            ModelSettings(name=self._name),   # default settings
        )

        # --- Weak model ---------------------------------------------------
        if weak_model is not None:
            self.weak_model: Optional[Model] = weak_model
        elif self.settings.weak_model_name:
            self.weak_model = Model(self.settings.weak_model_name)
        else:
            self.weak_model = None

        # --- Editor model -------------------------------------------------
        if editor_model is not None:
            self.editor_model: Optional[Model] = editor_model
        elif self.settings.editor_model_name:
            self.editor_model = Model(self.settings.editor_model_name)
        else:
            self.editor_model = None

    # -----------------------------------------------------------------------
    # Properties
    # -----------------------------------------------------------------------

    @property
    def name(self) -> str:
        """The canonical LiteLLM model string."""
        return self._name

    @property
    def info(self) -> Dict[str, Any]:
        """LiteLLM model metadata (costs, context-window size, etc.)."""
        return get_model_info(self._name)

    @property
    def max_context_tokens(self) -> Optional[int]:
        """The model's context-window size in tokens, or *None* if unknown.

        Uses LiteLLM's ``max_input_tokens`` field when available, falling
        back to ``max_tokens`` (which sometimes represents the context window
        rather than the completion limit).
        """
        info = self.info
        return (
            info.get("max_input_tokens")
            or info.get("max_tokens")
            or None
        )

    # -----------------------------------------------------------------------
    # Token counting
    # -----------------------------------------------------------------------

    def token_count(self, messages: List[Dict[str, str]]) -> int:
        """Estimate the number of tokens consumed by *messages*.

        Uses ``litellm.token_counter`` when available; falls back to a rough
        word-based approximation when the tokeniser for this model is unknown.

        Parameters
        ----------
        messages:
            Chat-format message list.

        Returns
        -------
        int
            Estimated token count.
        """
        try:
            return litellm.token_counter(model=self._name, messages=messages)
        except Exception as exc:
            logger.debug(
                "token_count: litellm.token_counter failed for %r: %s",
                self._name,
                exc,
            )
            # Rough fallback: ~4 characters per token on average.
            total_chars = sum(
                len(msg.get("content", "")) for msg in messages
            )
            return total_chars // 4

    # -----------------------------------------------------------------------
    # Sending messages
    # -----------------------------------------------------------------------

    def send_with_retries(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> Any:
        """Send *messages* and return the raw LiteLLM completion object.

        Delegates to :func:`reviewforge.sendchat.send_with_retries` with
        this model's name and default temperature.
        """
        temperature = kwargs.pop("temperature", self.settings.use_temperature)
        stream = kwargs.pop("stream", self.settings.streaming)
        return sendchat.send_with_retries(
            model_name=self._name,
            messages=messages,
            temperature=temperature,
            stream=stream,
            **kwargs,
        )

    def simple_send_with_retries(
        self,
        messages: List[Dict[str, str]],
        **kwargs: Any,
    ) -> Optional[str]:
        """Send *messages* and return only the reply text.

        Delegates to :func:`reviewforge.sendchat.simple_send_with_retries`.
        """
        temperature = kwargs.pop("temperature", self.settings.use_temperature)
        return sendchat.simple_send_with_retries(
            model_name=self._name,
            messages=messages,
            temperature=temperature,
            **kwargs,
        )

    # -----------------------------------------------------------------------
    # Multi-model helpers
    # -----------------------------------------------------------------------

    def commit_message_models(self) -> List["Model"]:
        """Return the ordered list of models to try for commit-message generation.

        ReviewForge tries the weak model first (it's cheaper and fast enough
        for short summaries), then falls back to the main model.

        Returns
        -------
        list[Model]
            ``[weak_model, self]`` when a weak model is configured, otherwise
            just ``[self]``.
        """
        if self.weak_model and self.weak_model is not self:
            return [self.weak_model, self]
        return [self]

    # -----------------------------------------------------------------------
    # Dunder methods
    # -----------------------------------------------------------------------

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        weak = (
            f", weak_model={self.weak_model!r}"
            if self.weak_model
            else ""
        )
        editor = (
            f", editor_model={self.editor_model!r}"
            if self.editor_model
            else ""
        )
        return f"Model({self._name!r}{weak}{editor})"


# ---------------------------------------------------------------------------
# sanity_check_models
# ---------------------------------------------------------------------------

def sanity_check_models(io: Any, main_model: Model) -> bool:
    """Check that *main_model* (and its sub-models) look valid.

    Emits warnings through *io* (which must expose a ``.warning(msg)`` or
    ``.print_warning(msg)`` method, or a plain callable) for any model that
    is not in LiteLLM's metadata database.

    Parameters
    ----------
    io:
        ReviewForge IO object (or any object with a ``warning`` / callable
        interface used to display user-facing messages).
    main_model:
        The main :class:`Model` to check.

    Returns
    -------
    bool
        *True* when all models pass the checks, *False* when any warning was
        emitted.
    """
    def _warn(msg: str) -> None:
        if hasattr(io, "warning"):
            io.warning(msg)
        elif hasattr(io, "print_warning"):
            io.print_warning(msg)
        elif callable(io):
            io(msg)
        else:
            logger.warning(msg)

    all_ok = True

    for label, model in [
        ("Main model", main_model),
        ("Weak model", main_model.weak_model),
        ("Editor model", main_model.editor_model),
    ]:
        if model is None:
            continue

        info = model.info
        if not info:
            _warn(
                f"{label} {model.name!r} is not found in LiteLLM's model "
                "database. It may still work if the provider supports it, "
                "but token counting and cost tracking will be unavailable."
            )
            all_ok = False
        else:
            logger.debug("%s %r: info=%s", label, model.name, info)

    return all_ok


# ---------------------------------------------------------------------------
# register_models (YAML loader)
# ---------------------------------------------------------------------------

def register_models(model_settings_fname: str) -> List[ModelSettings]:
    """Load additional ``ModelSettings`` from a YAML file and register them.

    The YAML file should contain a top-level ``models`` key whose value is a
    list of mapping objects.  Each mapping must have at least a ``name`` key;
    all other keys correspond to ``ModelSettings`` field names.

    Example YAML
    ------------
    .. code-block:: yaml

        models:
          - name: my-org/private-model
            edit_format: whole
            use_repo_map: false
            max_tokens: 8192

    Parameters
    ----------
    model_settings_fname:
        Absolute or relative path to the YAML configuration file.

    Returns
    -------
    list[ModelSettings]
        The newly registered ``ModelSettings`` objects.

    Raises
    ------
    FileNotFoundError
        When the file does not exist.
    ValueError
        When the YAML is malformed or missing required fields.
    """
    with open(model_settings_fname, "r", encoding="utf-8") as fh:

        raw = yaml.safe_load(fh)

    if not isinstance(raw, dict) or "models" not in raw:
        raise ValueError(
            f"YAML file {model_settings_fname!r} must have a top-level "
            "'models' key containing a list of model configurations."
        )

    entries = raw["models"]
    if not isinstance(entries, list):
        raise ValueError("'models' must be a list of model configuration dicts.")

    # Valid field names from the dataclass.
    valid_field_names = {f.name for f in fields(ModelSettings)}
    registered: List[ModelSettings] = []

    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(
                f"Each model entry must be a dict; got {type(entry).__name__}."
            )
        if "name" not in entry:
            raise ValueError(
                f"Model entry is missing required 'name' key: {entry!r}"
            )

        # Filter to only known fields so unknown YAML keys don't break the
        # dataclass constructor.
        known_kwargs = {k: v for k, v in entry.items() if k in valid_field_names}
        unknown_keys = set(entry) - valid_field_names
        if unknown_keys:
            logger.warning(
                "register_models: unknown field(s) %s in entry for model %r; "
                "they will be ignored.",
                unknown_keys,
                entry.get("name"),
            )

        ms = ModelSettings(**known_kwargs)
        KNOWN_MODELS.append(ms)
        _KNOWN_MODELS_BY_NAME[ms.name] = ms
        registered.append(ms)
        logger.debug("register_models: registered %r", ms.name)

    return registered


# ---------------------------------------------------------------------------
# Module public surface
# ---------------------------------------------------------------------------

__all__ = [
    "DEFAULT_MODEL_NAME",
    "MODEL_ALIASES",
    "ModelSettings",
    "KNOWN_MODELS",
    "Model",
    "sanity_check_models",
    "register_models",
    "get_model_info",
]
