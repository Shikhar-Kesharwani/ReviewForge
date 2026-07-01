"""
reviewforge/analytics.py

Optional, anonymous telemetry for ReviewForge.

Analytics are **disabled by default**.  Users must explicitly opt in (either
via --analytics on the CLI or by responding "yes" to the one-time prompt).
When enabled, events can be sent to PostHog or written to a local log file.
All identifiers are random UUIDs — no PII is collected.
"""

import json
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path.home() / ".reviewforge"
_ANALYTICS_CONFIG = _CONFIG_DIR / "analytics.json"


# ---------------------------------------------------------------------------
# Analytics class
# ---------------------------------------------------------------------------

class Analytics:
    """
    Lightweight analytics client for ReviewForge.

    All public methods are safe to call regardless of whether analytics are
    enabled — they become no-ops when ``enabled=False``.

    Parameters
    ----------
    enabled      : bool
        Master switch.  When False every method returns immediately.
    log_file     : str | Path | None
        If provided and enabled, events are appended as JSON lines to this
        file in addition to (or instead of) PostHog.
    posthog_key  : str | None
        PostHog project API key.  When None, PostHog is not used.
    posthog_host : str | None
        PostHog host URL.  Defaults to 'https://app.posthog.com'.
    """

    def __init__(
        self,
        enabled: bool = False,
        log_file=None,
        posthog_key: Optional[str] = None,
        posthog_host: Optional[str] = None,
    ):
        self.enabled = enabled
        self.log_file = Path(log_file) if log_file else None
        self.posthog_key = posthog_key
        self.posthog_host = posthog_host or "https://app.posthog.com"

        # Super-properties are merged into every event
        self._super_properties: Dict[str, Any] = {}

        # Lazy PostHog client — only imported / initialised when needed
        self._posthog = None

        if enabled:
            self._user_id = self.get_or_create_user_id()
            if posthog_key:
                self._init_posthog()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_posthog(self) -> None:
        """Attempt to import and initialise the posthog client library."""
        try:
            import posthog as _ph  # type: ignore

            _ph.project_api_key = self.posthog_key
            _ph.host = self.posthog_host
            # Disable PostHog's own debug logging
            _ph.debug = False
            self._posthog = _ph
        except ImportError:
            # posthog library not installed — fall back to log-file only
            self._posthog = None

    def _write_log(self, name: str, properties: Dict[str, Any]) -> None:
        """Append a single event as a JSON line to the log file."""
        if not self.log_file:
            return
        try:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "event": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": getattr(self, "_user_id", "unknown"),
                "properties": properties,
            }
            with self.log_file.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except OSError:
            pass  # non-fatal

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def event(self, name: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """
        Track a named event.

        Parameters
        ----------
        name       : str
            Event name, e.g. 'review_started', 'command_executed'.
        properties : dict | None
            Arbitrary key/value pairs describing the event.
        """
        if not self.enabled:
            return

        merged: Dict[str, Any] = {}
        merged.update(self._super_properties)
        if properties:
            merged.update(properties)

        # Send to PostHog if available
        if self._posthog is not None:
            try:
                self._posthog.capture(
                    distinct_id=self._user_id,
                    event=name,
                    properties=merged,
                )
            except Exception:
                pass  # never let analytics crash the app

        # Always write to log file if configured
        self._write_log(name, merged)

    def set_property(self, key: str, value: Any) -> None:
        """
        Set a super-property that will be included with every future event.

        Parameters
        ----------
        key   : str
            Property name.
        value : Any
            Property value (must be JSON-serialisable).
        """
        if not self.enabled:
            return
        self._super_properties[key] = value

    def get_or_create_user_id(self) -> str:
        """
        Load the anonymous user UUID from disk, creating one if absent.

        The UUID is stored in ``~/.reviewforge/analytics.json``.  It is a
        random v4 UUID with no relationship to any personal identifier.

        Returns
        -------
        str
            A UUID4 string, e.g. 'a1b2c3d4-e5f6-...'.
        """
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if _ANALYTICS_CONFIG.exists():
                with _ANALYTICS_CONFIG.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                user_id = data.get("user_id")
                if user_id:
                    return str(user_id)
        except (OSError, json.JSONDecodeError):
            pass

        # Create a fresh UUID and persist it
        new_id = str(uuid.uuid4())
        try:
            existing: Dict[str, Any] = {}
            if _ANALYTICS_CONFIG.exists():
                with _ANALYTICS_CONFIG.open("r", encoding="utf-8") as fh:
                    existing = json.load(fh)
            existing["user_id"] = new_id
            with _ANALYTICS_CONFIG.open("w", encoding="utf-8") as fh:
                json.dump(existing, fh, indent=2)
        except OSError:
            pass

        return new_id

    def disable_forever(self) -> None:
        """
        Permanently opt the user out of analytics.

        Writes ``{"disabled": true}`` into the analytics config and sets
        ``self.enabled = False`` immediately.
        """
        self.enabled = False
        try:
            _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            existing: Dict[str, Any] = {}
            if _ANALYTICS_CONFIG.exists():
                with _ANALYTICS_CONFIG.open("r", encoding="utf-8") as fh:
                    existing = json.load(fh)
            existing["disabled"] = True
            with _ANALYTICS_CONFIG.open("w", encoding="utf-8") as fh:
                json.dump(existing, fh, indent=2)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def _is_permanently_disabled() -> bool:
    """Return True if the user has opted out permanently."""
    try:
        if _ANALYTICS_CONFIG.exists():
            with _ANALYTICS_CONFIG.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return bool(data.get("disabled", False))
    except (OSError, json.JSONDecodeError):
        pass
    return False


def setup_analytics(args, io) -> Analytics:
    """
    Factory function that reads CLI args and constructs an ``Analytics`` instance.

    Decision logic:
    1. If the user has previously opted out permanently → disabled.
    2. If ``--analytics-disable`` was passed → disable and save opt-out.
    3. If ``--analytics`` was passed → enable.
    4. If ``args.analytics`` is None (first run) → offer an opt-in prompt
       to a random 10 % of users (sampling avoids pestering everyone).

    Parameters
    ----------
    args : argparse.Namespace
        Must have optional attributes: ``analytics`` (bool|None),
        ``analytics_disable`` (bool), ``analytics_log`` (str|None),
        ``posthog_key`` (str|None).
    io   : reviewforge IO object
        Must expose ``confirm(question) -> bool`` and ``tool_output(msg)``.

    Returns
    -------
    Analytics
        A fully configured (but possibly disabled) Analytics instance.
    """
    # Permanent opt-out takes precedence over everything
    if _is_permanently_disabled():
        return Analytics(enabled=False)

    log_file = getattr(args, "analytics_log", None)
    posthog_key = getattr(args, "posthog_key", None)

    # Explicit opt-out via CLI
    if getattr(args, "analytics_disable", False):
        instance = Analytics(enabled=False)
        instance.disable_forever()
        io.tool_output("Analytics disabled permanently.")
        return instance

    # Explicit opt-in via CLI
    analytics_flag = getattr(args, "analytics", None)
    if analytics_flag is True:
        return Analytics(
            enabled=True,
            log_file=log_file,
            posthog_key=posthog_key,
        )

    # First-run: offer opt-in to a random 10 % sample
    if analytics_flag is None:
        sampled = random.random() < 0.10
        if sampled:
            try:
                wants = io.confirm(
                    "Help improve ReviewForge by sharing anonymous usage data? "
                    "(no code or file content is ever sent)"
                )
            except (EOFError, KeyboardInterrupt):
                wants = False

            if wants:
                io.tool_output(
                    "Anonymous analytics enabled. "
                    "Run with --analytics-disable to opt out at any time."
                )
                return Analytics(
                    enabled=True,
                    log_file=log_file,
                    posthog_key=posthog_key,
                )

    return Analytics(enabled=False)
