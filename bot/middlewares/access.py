"""
Middlewares for the Onboarding Bot.
"""
from typing import Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from bot.config import settings
from bot.logger import get_logger

logger = get_logger(__name__)


class AccessControlMiddleware(BaseMiddleware):
    """Middleware for access control."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable],
        event: TelegramObject,
        data: dict,
    ) -> None:
        """Check if user is allowed to use the bot."""
        user: User = data.get("event_from_user")
        
        if user:
            data["user_id"] = user.id
            data["username"] = user.username
            data["is_admin"] = user.id in settings.admin_ids_list
            data["is_creator"] = user.id in settings.allowed_creators_list
        
        return await handler(event, data)


def is_allowed_creator(user_id: int) -> bool:
    """Check if user is allowed to create hires."""
    return user_id in settings.allowed_creators_list


def is_admin(user_id: int) -> bool:
    """Check if user is an admin."""
    return user_id in settings.admin_ids_list


def is_creator_or_admin(user_id: int) -> bool:
    """Check if user is creator or admin."""
    return is_allowed_creator(user_id) or is_admin(user_id)
