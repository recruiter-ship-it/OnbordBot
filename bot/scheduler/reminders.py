"""
Scheduler for reminders and escalations.
"""
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
import pytz

from bot.config import settings
from bot.database import get_session
from bot.database.models import (
    Hire,
    HireStatus,
    LegalStatus,
    DevOpsStatus,
)
from bot.services.hire_service import HireService
from bot.utils.formatting import format_hire_card, days_until
from bot.logger import get_logger

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


async def send_reminders(bot) -> None:
    """Check and send reminders for all hires."""
    logger.info("Running reminder check")
    
    tz = pytz.timezone(settings.TIMEZONE)
    now = datetime.now(tz)
    
    async with get_session() as session:
        hire_service = HireService(session)
        
        # Get all open hires
        hires = await hire_service.get_open_hires()
        
        for hire in hires:
            try:
                await _check_legal_reminder(bot, hire, hire_service, now)
                await _check_devops_reminder(bot, hire, hire_service, now)
                await _check_escalation(bot, hire, hire_service, now)
            except Exception as e:
                logger.error(
                    "Error processing hire reminders",
                    hire_id=hire.hire_id,
                    error=str(e),
                )


async def _check_legal_reminder(
    bot, 
    hire: Hire, 
    hire_service: HireService,
    now: datetime
) -> None:
    """Check if legal reminder is needed."""
    if hire.legal_status == LegalStatus.DOCS_SENT:
        return
    
    if hire.legal_reminded:
        return
    
    days = days_until(hire.start_date)
    
    # Remind if within threshold days before start
    if 0 < days <= settings.LEGAL_REMINDER_DAYS:
        # Send reminder
        message = (
            f"⚠️ <b>Напоминание Legal</b>\n\n"
            f"До выхода #{hire.hire_id} ({hire.full_name}) осталось {days} дн.\n"
            f"Документы ещё не отправлены!\n\n"
            f"@{hire.legal_username} — пожалуйста, подготовьте документы для {hire.docs_email}"
        )
        
        try:
            # Send to chat
            await bot.send_message(
                chat_id=settings.ONBOARDING_CHAT_ID,
                text=message,
                parse_mode="HTML",
            )
            
            # Mark as reminded
            await hire_service.mark_legal_reminded(hire.hire_id)
            
            logger.info(
                "Legal reminder sent",
                hire_id=hire.hire_id,
                days_until_start=days,
            )
        except Exception as e:
            logger.error("Failed to send legal reminder", error=str(e))


async def _check_devops_reminder(
    bot, 
    hire: Hire, 
    hire_service: HireService,
    now: datetime
) -> None:
    """Check if DevOps reminder is needed."""
    if hire.devops_status == DevOpsStatus.ACCESS_GRANTED:
        return
    
    if hire.devops_reminded:
        return
    
    days = days_until(hire.start_date)
    
    # Remind if within threshold days before start
    if 0 < days <= settings.DEVOPS_REMINDER_DAYS:
        # Send reminder
        message = (
            f"⚠️ <b>Напоминание DevOps</b>\n\n"
            f"До выхода #{hire.hire_id} ({hire.full_name}) осталось {days} дн.\n"
            f"Доступы ещё не выданы!\n\n"
            f"@{hire.devops_username} — пожалуйста, настройте доступы"
        )
        
        try:
            # Send to chat
            await bot.send_message(
                chat_id=settings.ONBOARDING_CHAT_ID,
                text=message,
                parse_mode="HTML",
            )
            
            # Mark as reminded
            await hire_service.mark_devops_reminded(hire.hire_id)
            
            logger.info(
                "DevOps reminder sent",
                hire_id=hire.hire_id,
                days_until_start=days,
            )
        except Exception as e:
            logger.error("Failed to send devops reminder", error=str(e))


async def _check_escalation(
    bot, 
    hire: Hire, 
    hire_service: HireService,
    now: datetime
) -> None:
    """Check if escalation is needed."""
    if hire.escalated:
        return
    
    days = days_until(hire.start_date)
    
    # Check if past start date and overdue
    if days < 0:
        hours_overdue = abs(days) * 24
        
        # Check if any status is still pending and overdue
        has_pending = (
            hire.legal_status != LegalStatus.DOCS_SENT or
            hire.devops_status != DevOpsStatus.ACCESS_GRANTED
        )
        
        if has_pending and hours_overdue >= settings.ESCALATION_HOURS:
            # Send escalation
            message = (
                f"🚨 <b>ЭСКАЛАЦИЯ — Просрочка!</b>\n\n"
                f"Карточка #{hire.hire_id} ({hire.full_name}) просрочена!\n"
                f"Дата выхода была: {hire.start_date.strftime('%d.%m.%Y')}\n"
                f"Просрочка: {abs(days)} дн.\n\n"
                f"<b>Незавершённые задачи:</b>\n"
            )
            
            if hire.legal_status != LegalStatus.DOCS_SENT:
                message += f"• ⚖️ Legal (@{hire.legal_username}): документы не отправлены\n"
            if hire.devops_status != DevOpsStatus.ACCESS_GRANTED:
                message += f"• 🔧 DevOps (@{hire.devops_username}): доступы не выданы\n"
            
            message += f"\n📢 Рекрутер: создатель карточки ID {hire.creator_id}"
            
            try:
                # Send to chat
                await bot.send_message(
                    chat_id=settings.ONBOARDING_CHAT_ID,
                    text=message,
                    parse_mode="HTML",
                )
                
                # Also try to DM the creator
                try:
                    await bot.send_message(
                        chat_id=hire.creator_id,
                        text=f"🚨 Эскалация! Карточка #{hire.hire_id} просрочена. "
                             f"Проверьте чат онбординга.",
                    )
                except Exception:
                    pass  # Can't DM, that's OK
                
                # Mark as escalated
                await hire_service.mark_escalated(hire.hire_id)
                
                logger.warning(
                    "Escalation sent",
                    hire_id=hire.hire_id,
                    days_overdue=abs(days),
                )
            except Exception as e:
                logger.error("Failed to send escalation", error=str(e))


def setup_scheduler(bot) -> None:
    """Setup the scheduler with the bot instance."""
    scheduler.add_job(
        send_reminders,
        trigger=IntervalTrigger(minutes=settings.SCHEDULER_INTERVAL_MINUTES),
        args=[bot],
        id="reminder_job",
        replace_existing=True,
    )
    
    logger.info(
        "Scheduler configured",
        interval_minutes=settings.SCHEDULER_INTERVAL_MINUTES,
    )


def start_scheduler() -> None:
    """Start the scheduler."""
    scheduler.start()
    logger.info("Scheduler started")


def shutdown_scheduler() -> None:
    """Shutdown the scheduler."""
    scheduler.shutdown()
    logger.info("Scheduler shutdown")
