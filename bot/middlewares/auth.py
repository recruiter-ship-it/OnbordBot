"""
Middlewares for the Onboarding Bot.
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from bot.config import settings
from bot.logger import get_logger

logger = get_logger(__name__)


class AuthMiddleware(BaseMiddleware):
    """Middleware for checking user permissions."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Check if user is allowed to create hires."""
        user: User = data.get("event_from_user")
        
        if user:
            data["is_allowed_creator"] = user.id in settings.allowed_creators_list
            data["is_admin"] = user.id in settings.admin_ids_list
        
        return await handler(event, data)


class LoggingMiddleware(BaseMiddleware):
    """Middleware for logging all updates."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Log incoming updates."""
        user: User = data.get("event_from_user")
        
        if user:
            logger.debug(
                "Update received",
                user_id=user.id,
                username=user.username,
                update_type=type(event).__name__,
            )
        
        return await handler(event, data)
