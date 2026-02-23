"""
Bot package initialization.
"""
from bot.config import settings
from bot.logger import configure_logging, get_logger

__all__ = ["settings", "configure_logging", "get_logger"]
