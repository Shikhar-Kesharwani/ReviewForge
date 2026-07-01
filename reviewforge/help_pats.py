"""
reviewforge/help_pats.py

Help topic search patterns for ReviewForge.

Maps human-readable help topic keywords to glob patterns that match relevant
documentation files.  Used by the built-in ``/help`` command to quickly
surface the right docs for a given topic without requiring a full-text search.

Usage example
-------------
>>> from reviewforge.help_pats import HELP_PATS
>>> patterns = HELP_PATS.get("model", [])
>>> # patterns == ['*model*', '*llm*']
"""

from typing import Dict, List


#: Mapping from help-topic keyword to a list of documentation file glob
#: patterns.  Each pattern will be matched against documentation file paths
#: (case-insensitively) to find relevant pages for the user's query.
HELP_PATS: Dict[str, List[str]] = {
    # Installation and first-time setup docs.
    "install": [
        "*install*",
        "*setup*",
        "*getting-started*",
        "*quickstart*",
    ],
    # LLM / model configuration.
    "model": [
        "*model*",
        "*llm*",
        "*provider*",
    ],
    # Git integration.
    "git": [
        "*git*",
    ],
    # Voice / speech input mode.
    "voice": [
        "*voice*",
        "*speech*",
        "*audio*",
    ],
    # Configuration files and settings.
    "config": [
        "*config*",
        "*settings*",
        "*options*",
        "*env*",
    ],
    # Editing / patch-apply workflow.
    "edit": [
        "*edit*",
        "*patch*",
        "*diff*",
        "*apply*",
    ],
    # Usage / commands reference.
    "usage": [
        "*usage*",
        "*command*",
        "*cli*",
        "*reference*",
    ],
    # Troubleshooting and FAQ.
    "troubleshoot": [
        "*troubleshoot*",
        "*faq*",
        "*problem*",
        "*error*",
        "*fix*",
    ],
}
