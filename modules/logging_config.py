"""
Global Logging Configuration for Trading System

This module provides a centralized logging setup using the logger_module.
It creates a single global logger instance that can be used throughout the application.

Usage:
    from modules.logging_config import logger
    logger.info("Application started")
"""

from .logger_module import setup_logging

# Global logger instance for the entire application
logger = setup_logging(
    log_dir='logs',
    log_file_prefix='Trading_Bot'
)

def get_logger():
    """
    Return the global logger instance.

    This function provides a consistent way to access the logger
    and allows for future flexibility (e.g., different loggers for different modules).

    Returns:
        logging.Logger: The configured logger instance
    """
    return logger

# Export the logger for direct import
__all__ = ['logger', 'get_logger']