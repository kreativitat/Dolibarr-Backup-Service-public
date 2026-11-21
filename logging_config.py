#!/usr/bin/env python3
"""
Logging configuration for the backup service.
Provides both console and file logging with rotation.
"""
import logging
import logging.handlers
import os
from typing import Optional


def setup_logging(
    log_file: str = "/logs/backup.log",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5,
    console_output: bool = True
) -> logging.Logger:
    """
    Configure logging with file rotation and console output.

    Args:
        log_file: Path to the log file
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        console_output: Whether to output to console as well

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger('dolibarr_backup')
    logger.setLevel(getattr(logging, log_level.upper()))

    # Clear any existing handlers
    logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # File handler with rotation
    try:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file handler: {e}")

    # Console handler
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def setup_json_logging(
    log_file: str = "/logs/backup_json.log",
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,
    backup_count: int = 5
) -> logging.Logger:
    """
    Configure JSON structured logging for better parsing.

    Args:
        log_file: Path to the JSON log file
        log_level: Logging level
        max_bytes: Maximum size before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance
    """
    import json
    import datetime

    class JsonFormatter(logging.Formatter):
        """Custom formatter to output logs as JSON."""

        def format(self, record: logging.LogRecord) -> str:
            log_data = {
                'timestamp': datetime.datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'logger': record.name,
                'message': record.getMessage(),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno
            }

            if record.exc_info:
                log_data['exception'] = self.formatException(record.exc_info)

            return json.dumps(log_data)

    # Create logs directory
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # Create logger
    logger = logging.getLogger('dolibarr_backup_json')
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.handlers.clear()

    # JSON file handler
    try:
        json_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(JsonFormatter())
        logger.addHandler(json_handler)
    except Exception as e:
        print(f"Warning: Could not create JSON handler: {e}")

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Optional logger name. If None, returns root logger.

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(name)
    return logging.getLogger('dolibarr_backup')
