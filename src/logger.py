import logging
import logging.handlers
from pathlib import Path
import asyncio

class RedactingFormatter(logging.Formatter):
    """Formatter to ensure API keys and secrets are never logged."""
    def __init__(self, orig_formatter: logging.Formatter):
        self.orig_formatter = orig_formatter

    def format(self, record: logging.LogRecord) -> str:
        msg = self.orig_formatter.format(record)
        # Redact common sensitive keywords if they slip into log messages
        sensitive_keys = ["api_key", "secret", "password", "webhook"]
        for key in sensitive_keys:
            if key in msg.lower():
                msg = f"[REDACTED SENSITIVE {key.upper()} DATA]"
        return msg

def setup_logger(name: str, log_file: str, level: int = logging.INFO) -> logging.Logger:
    """Sets up an asynchronous-safe logger with redacting format."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if logger.hasHandlers():
        logger.handlers.clear()

    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(module)s | %(message)s')
    redacting_formatter = RedactingFormatter(formatter)

    # File Handler
    file_handler = logging.FileHandler(log_dir / log_file)
    file_handler.setFormatter(redacting_formatter)
    
    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(redacting_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Pre-configured loggers
trading_logger = setup_logger("trading", "trading.log")
error_logger = setup_logger("error", "errors.log", logging.ERROR)
api_logger = setup_logger("api", "api.log")
