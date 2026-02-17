"""
Main entry point for the Onboarding Bot.
"""
import asyncio
import signal
import sys
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot import configure_logging, get_logger, settings
from bot.database import init_db, close_db
from bot.middlewares.auth import AuthMiddleware, LoggingMiddleware
from bot.handlers.newhire import router as newhire_router
from bot.handlers.callbacks import router as callbacks_router
from bot.handlers.commands import router as commands_router
from bot.services.scheduler import (
    setup_scheduler,
    start_scheduler,
    shutdown_scheduler,
)

logger = get_logger(__name__)

# Global bot and dispatcher instances
bot: Bot = None
dp: Dispatcher = None


async def on_startup():
    """Actions to perform on bot startup."""
    logger.info("Starting bot...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Setup scheduler
    setup_scheduler(bot)
    start_scheduler()
    logger.info("Scheduler started")
    
    # Log configuration
    logger.info(
        "Bot configuration",
        timezone=settings.TIMEZONE,
        onboarding_chat_id=settings.ONBOARDING_CHAT_ID,
        allowed_creators_count=len(settings.allowed_creators_list),
        admin_count=len(settings.admin_ids_list),
    )


async def on_shutdown():
    """Actions to perform on bot shutdown."""
    logger.info("Shutting down bot...")
    
    # Shutdown scheduler
    shutdown_scheduler()
    
    # Close database
    await close_db()
    
    # Close bot session
    if bot:
        await bot.session.close()
    
    logger.info("Bot shutdown complete")


def setup_dispatcher():
    """Setup dispatcher with routers and middlewares."""
    global dp
    
    dp = Dispatcher()
    
    # Add middlewares
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    dp.message.middleware(LoggingMiddleware())
    dp.callback_query.middleware(LoggingMiddleware())
    
    # Register routers
    dp.include_router(newhire_router)
    dp.include_router(callbacks_router)
    dp.include_router(commands_router)
    
    # Start command handler
    @dp.message(CommandStart())
    async def cmd_start(message: Message, is_allowed_creator: bool = False):
        """Handle /start command."""
        welcome_text = """
👋 <b>Добро пожаловать в бот онбординга!</b>

Этот бот помогает автоматизировать процесс выхода новых сотрудников.

"""
        if is_allowed_creator:
            welcome_text += """
✅ У вас есть права на создание карточек.

Используйте /newhire для создания карточки нового сотрудника.
"""
        else:
            welcome_text += """
ℹ️ Вы можете просматривать статусы карточек в общем чате.
Для создания карточек обратитесь к администратору.
"""
        
        welcome_text += "\n📝 /help — справка по командам"
        
        await message.answer(welcome_text, parse_mode="HTML")
    
    return dp


async def main():
    """Main function to run the bot."""
    global bot
    
    # Configure logging
    configure_logging()
    
    # Create bot instance
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    # Setup dispatcher
    setup_dispatcher()
    
    # Run startup actions
    await on_startup()
    
    try:
        # Start polling
        logger.info("Starting polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    finally:
        # Run shutdown actions
        await on_shutdown()


def run():
    """Entry point for running the bot."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        logger.error("Bot crashed", error=str(e), exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run()
