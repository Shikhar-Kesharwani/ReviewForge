"""
Structured JSON Logger for ReviewForge.
Outputs structured JSON logs including Timestamp, Level, Request ID, Correlation ID, and Environment.
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone


class JSONFormatter(logging.Formatter):
    """Custom logging formatter that outputs JSON strings."""
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "environment": os.getenv("ENVIRONMENT", "development"),
            "service": "reviewforge-backend",
        }
        
        # Include extra context attributes if provided
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
            
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_logger(name: str = "reviewforge") -> logging.Logger:
    """Configures and returns a structured JSON logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)
        logger.setLevel(log_level)
        
    return logger


# Global Singleton Logger
logger = get_logger()
