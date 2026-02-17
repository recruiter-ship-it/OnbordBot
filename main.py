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

from bot.config import settings
from bot.database import init_db, close_db
from bot.logger import configure_logging, get_logger
from bot.handlers import newhire, callbacks, commands
from bot.scheduler.reminders import (
    setup_scheduler, 
    start_scheduler, 
    shutdown_scheduler,
)

# Configure logging
configure_logging()
logger = get_logger(__name__)


# Global bot and dispatcher
bot: Bot = None
dp: Dispatcher = None


async def on_startup() -> None:
    """Actions to perform on startup."""
    logger.info("Starting Onboarding Bot...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Setup scheduler
    setup_scheduler(bot)
    start_scheduler()
    logger.info("Scheduler started")
    
    # Send startup notification to chat (optional)
    try:
        if settings.ONBOARDING_CHAT_ID:
            await bot.send_message(
                chat_id=settings.ONBOARDING_CHAT_ID,
                text="🤖 Onboarding Bot запущен и готов к работе!",
            )
    except Exception as e:
        logger.warning("Could not send startup notification", error=str(e))
    
    logger.info("Onboarding Bot started successfully")


async def on_shutdown() -> None:
    """Actions to perform on shutdown."""
    logger.info("Shutting down Onboarding Bot...")
    
    # Stop scheduler
    shutdown_scheduler()
    
    # Close database
    await close_db()
    
    # Send shutdown notification
    try:
        if settings.ONBOARDING_CHAT_ID:
            await bot.send_message(
                chat_id=settings.ONBOARDING_CHAT_ID,
                text="🤖 Onboarding Bot остановлен.",
            )
    except Exception as e:
        logger.warning("Could not send shutdown notification", error=str(e))
    
    # Close bot session
    await bot.session.close()
    
    logger.info("Onboarding Bot shutdown complete")


def setup_handlers() -> None:
    """Setup all handlers."""
    # Create dispatcher
    global dp
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(commands.router)
    dp.include_router(newhire.router)
    dp.include_router(callbacks.router)
    
    logger.info("Handlers registered")


async def main() -> None:
    """Main function."""
    global bot
    
    # Validate configuration
    if not settings.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        sys.exit(1)
    
    if not settings.ONBOARDING_CHAT_ID:
        logger.warning("ONBOARDING_CHAT_ID is not set! Bot may not work correctly.")
    
    # Create bot instance
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    
    # Setup handlers
    setup_handlers()
    
    # Run startup
    await on_startup()
    
    # Setup signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        logger.info("Received shutdown signal")
        asyncio.create_task(on_shutdown())
    
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support add_signal_handler
            pass
    
    try:
        # Start polling
        logger.info("Starting polling...")
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
        )
    except asyncio.CancelledError:
        logger.info("Polling cancelled")
    finally:
        await on_shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Fatal error", error=str(e), exc_info=True)
        sys.exit(1)
