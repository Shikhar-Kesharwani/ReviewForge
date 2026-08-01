"""
Sentry Error Monitoring Integration for ReviewForge.
Initializes Sentry SDK if SENTRY_DSN environment variable is provided.
"""

import os


def init_sentry():
    """Initialize Sentry error tracking if SENTRY_DSN is configured."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("ENVIRONMENT", "development"),
            traces_sample_rate=0.2 if os.getenv("ENVIRONMENT") == "production" else 1.0,
            integrations=[FastApiIntegration()],
        )
        print("🟢 Sentry Error Tracking Initialized Successfully.")
        return True
    except ImportError:
        print("ℹ Sentry SDK not installed. Install with: pip install sentry-sdk")
        return False
    except Exception as e:
        print(f"⚠️ Failed to initialize Sentry: {e}")
        return False
