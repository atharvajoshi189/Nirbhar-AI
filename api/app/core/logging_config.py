import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

class StructuredJSONFormatter(logging.Formatter):
    """Formats log records into machine-parsable JSON Lines (JSONL)."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include request_id if present
        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id

        # Include structured telemetry
        if hasattr(record, "telemetry"):
            log_obj.update(record.telemetry)

        # Include exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj, default=str)

def setup_structured_logging(level: int = logging.INFO):
    """Configures root logger to use StructuredJSONFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())
    root_logger.addHandler(handler)

    # Quiet overly noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

