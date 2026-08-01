"""
Startup Environment Configuration Validator for ReviewForge.
Validates environment variables on boot and logs warnings/errors.
In production mode, raises RuntimeError if critical configuration is missing.
"""

import os
import sys


def validate_config(strict: bool = False) -> dict:
    """
    Validate environment variables.
    If strict=True (or ENVIRONMENT=production), raises RuntimeError on missing critical variables.
    """
    env = os.getenv("ENVIRONMENT", "development").lower()
    is_prod = env == "production" or strict

    warnings = []
    errors = []

    # Check LLM API Keys
    gemini_key = os.getenv("GEMINI_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not any([gemini_key, openai_key, anthropic_key]):
        warnings.append("No LLM API keys set (GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY). LLM calls will require runtime keys.")

    # Check Database setup
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        warnings.append("DATABASE_URL not set. ReviewForge will fall back to local SQLite at ./data/local.db.")

    # Check Cors Setup
    allowed_origins = os.getenv("ALLOWED_ORIGINS")
    if is_prod and not allowed_origins:
        errors.append("ALLOWED_ORIGINS must be set in production mode!")

    # Check Port
    port = os.getenv("PORT", "8000")
    if not port.isdigit():
        errors.append(f"Invalid PORT environment variable: '{port}'. Must be numeric.")

    if errors:
        error_msg = "CRITICAL CONFIGURATION ERROR(S):\n" + "\n".join(f"  - {e}" for e in errors)
        print(error_msg, file=sys.stderr)
        if is_prod:
            raise RuntimeError(error_msg)

    if warnings:
        print("CONFIGURATION NOTICE(S):")
        for w in warnings:
            print(f"  ℹ {w}")

    return {
        "environment": env,
        "is_production": is_prod,
        "has_llm_key": bool(gemini_key or openai_key or anthropic_key),
        "has_cloud_db": bool(db_url),
        "has_pinecone": bool(os.getenv("PINECONE_API_KEY")),
        "warnings_count": len(warnings),
        "errors_count": len(errors),
    }
