"""
Scheduler for reminders and escalations.
Uses APScheduler for periodic tasks.
"""
from datetime import datetime, timedelta
from typing import Optional
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from bot.config import settings
from bot.database import get_session, HireStatus
from bot.database.models import LeaderStatus, LegalStatus, DevOpsStatus, Hire
from bot.services.hire_service import HireService
from bot.utils.date_utils import format_date, days_until, get_now
from bot.logger import get_logger

logger = get_logger(__name__)

# Scheduler instance
scheduler = AsyncIOScheduler(timezone=pytz.timezone(settings.TIMEZONE))


async def send_reminder(
    bot: Bot,
    chat_id: int,
    user_id: Optional[int],
    username: Optional[str],
    message: str,
    thread_id: Optional[int] = None,
) -> bool:
    """
    Send reminder to user (private message) and/or chat.
    Returns True if any message was sent successfully.
    """
    success = False
    
    # Try private message first
    if user_id:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode="HTML",
            )
            success = True
        except TelegramBadRequest as e:
            logger.warning(
                "Failed to send private reminder",
                user_id=user_id,
                error=str(e),
            )
    
    # Also post to chat
    if chat_id:
        try:
            mention = f"@{username}" if username else ""
            chat_message = f"{mention}\n\n{message}"
            
            await bot.send_message(
                chat_id=chat_id,
                text=chat_message,
                parse_mode="HTML",
            )
            success = True
        except TelegramBadRequest as e:
            logger.warning(
                "Failed to send chat reminder",
                chat_id=chat_id,
                error=str(e),
            )
    
    return success


async def check_reminders(bot: Bot):
    """Check all hires for needed reminders and escalations."""
    logger.info("Running reminder check")
    
    now = get_now()
    
    async with get_session() as session:
        hire_service = HireService(session)
        hires = await hire_service.get_hires_needing_reminders()
        
        for hire in hires:
            if hire.status == HireStatus.COMPLETED:
                continue
            
            try:
                await process_hire_reminders(bot, hire, hire_service, now)
            except Exception as e:
                logger.error(
                    "Error processing hire reminders",
                    hire_id=hire.hire_id,
                    error=str(e),
                    exc_info=True,
                )


async def process_hire_reminders(
    bot: Bot,
    hire: Hire,
    hire_service: HireService,
    now: datetime,
):
    """Process reminders for a single hire."""
    days = days_until(hire.start_date)
    
    # Legal reminder: 3 days before start_date
    if (
        hire.legal_status == LegalStatus.PENDING and
        not hire.legal_reminded and
        days <= settings.LEGAL_REMINDER_DAYS and
        days > 0
    ):
        await send_legal_reminder(bot, hire, hire_service)
    
    # DevOps reminder: 1 day before start_date
    if (
        hire.devops_status == DevOpsStatus.PENDING and
        not hire.devops_reminded and
        days <= settings.DEVOPS_REMINDER_DAYS and
        days > 0
    ):
        await send_devops_reminder(bot, hire, hire_service)
    
    # Escalation: overdue by ESCALATION_HOURS
    if not hire.escalated and days < 0:
        # Check if any pending items
        has_pending = (
            hire.legal_status == LegalStatus.PENDING or
            hire.devops_status == DevOpsStatus.PENDING
        )
        
        if has_pending:
            overdue_hours = abs(days) * 24  # Rough estimate
            if overdue_hours >= settings.ESCALATION_HOURS:
                await send_escalation(bot, hire, hire_service)


async def send_legal_reminder(
    bot: Bot,
    hire: Hire,
    hire_service: HireService,
):
    """Send reminder to legal about pending documents."""
    message = f"""
⚠️ <b>Напоминание: Документы для нового сотрудника</b>

🎯 <b>Карточка #{hire.hire_id}</b>
👤 <b>ФИО:</b> {hire.full_name}
📅 <b>Дата выхода:</b> {format_date(hire.start_date)}
📧 <b>Почта:</b> {hire.docs_email}

Пожалуйста, отправьте документы и отметьте статус в чате онбординга.
"""
    
    success = await send_reminder(
        bot=bot,
        chat_id=hire.chat_id,
        user_id=hire.legal_id,
        username=hire.legal_username,
        message=message,
    )
    
    if success:
        await hire_service.mark_legal_reminded(hire.hire_id)
        logger.info(
            "Legal reminder sent",
            hire_id=hire.hire_id,
            legal_username=hire.legal_username,
        )


async def send_devops_reminder(
    bot: Bot,
    hire: Hire,
    hire_service: HireService,
):
    """Send reminder to devops about pending access."""
    message = f"""
⚠️ <b>Напоминание: Доступы для нового сотрудника</b>

🎯 <b>Карточка #{hire.hire_id}</b>
👤 <b>ФИО:</b> {hire.full_name}
📅 <b>Дата выхода:</b> {format_date(hire.start_date)} (завтра!)
💼 <b>Роль:</b> {hire.role}

Пожалуйста, настройте доступы и отметьте статус в чате онбординга.
"""
    
    success = await send_reminder(
        bot=bot,
        chat_id=hire.chat_id,
        user_id=hire.devops_id,
        username=hire.devops_username,
        message=message,
    )
    
    if success:
        await hire_service.mark_devops_reminded(hire.hire_id)
        logger.info(
            "DevOps reminder sent",
            hire_id=hire.hire_id,
            devops_username=hire.devops_username,
        )


async def send_escalation(
    bot: Bot,
    hire: Hire,
    hire_service: HireService,
):
    """Send escalation alert for overdue items."""
    days_overdue = abs(days_until(hire.start_date))
    
    pending_items = []
    if hire.legal_status == LegalStatus.PENDING:
        pending_items.append("⚖️ Документы от юриста")
    if hire.devops_status == DevOpsStatus.PENDING:
        pending_items.append("🔧 Доступы от DevOps")
    if hire.leader_status == LeaderStatus.PENDING:
        pending_items.append("👤 Подтверждение от лидера")
    
    pending_text = "\n".join([f"• {item}" for item in pending_items])
    
    # Message to creator
    creator_message = f"""
🚨 <b>ЭСКАЛАЦИЯ: Просрочка по онбордингу</b>

🎯 <b>Карточка #{hire.hire_id}</b>
👤 <b>ФИО:</b> {hire.full_name}
📅 <b>Дата выхода:</b> {format_date(hire.start_date)}
⚠️ <b>Просрочка:</b> {days_overdue} дн.

<b>Невыполненные задачи:</b>
{pending_text}

Требуется ваше вмешательство!
"""
    
    # Send to creator
    if hire.creator_id:
        try:
            await bot.send_message(
                chat_id=hire.creator_id,
                text=creator_message,
                parse_mode="HTML",
            )
        except TelegramBadRequest:
            pass
    
    # Post to chat
    chat_message = f"""
🚨 <b>ЭСКАЛАЦИЯ: Просрочка по онбордингу</b>

🎯 <b>Карточка #{hire.hire_id}</b>
👤 {hire.full_name}
📅 Дата выхода: {format_date(hire.start_date)}
⚠️ Просрочка: {days_overdue} дн.

<b>Невыполненные задачи:</b>
{pending_text}
"""
    
    try:
        await bot.send_message(
            chat_id=hire.chat_id,
            text=chat_message,
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        pass
    
    await hire_service.mark_escalated(hire.hire_id)
    logger.warning(
        "Escalation sent",
        hire_id=hire.hire_id,
        days_overdue=days_overdue,
    )


def setup_scheduler(bot: Bot):
    """Setup and start the scheduler."""
    
    async def check_job():
        """Wrapper for the check job."""
        await check_reminders(bot)
    
    # Add job to run periodically
    scheduler.add_job(
        check_job,
        trigger=IntervalTrigger(minutes=settings.SCHEDULER_INTERVAL_MINUTES),
        id="reminder_check",
        name="Check for pending reminders and escalations",
        replace_existing=True,
    )
    
    logger.info(
        "Scheduler configured",
        interval_minutes=settings.SCHEDULER_INTERVAL_MINUTES,
    )


def start_scheduler():
    """Start the scheduler."""
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    scheduler.shutdown(wait=True)
    logger.info("Scheduler shutdown")
