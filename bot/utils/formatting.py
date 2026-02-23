"""
Utility functions for the Onboarding Bot.
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
import pytz
from bot.config import settings
from bot.database.models import Hire, HireStatus, LeaderStatus, LegalStatus, DevOpsStatus


def get_timezone() -> pytz.timezone:
    """Get configured timezone."""
    return pytz.timezone(settings.TIMEZONE)


def parse_date(date_str: str) -> Optional[datetime]:
    """Parse date string in YYYY-MM-DD format."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Add timezone
        tz = get_timezone()
        return tz.localize(dt)
    except ValueError:
        return None


def format_datetime(dt: datetime) -> str:
    """Format datetime for display."""
    tz = get_timezone()
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    return dt.strftime("%d.%m.%Y %H:%M")


def format_date(dt: datetime) -> str:
    """Format date for display."""
    tz = get_timezone()
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    return dt.strftime("%d.%m.%Y")


def days_until(dt: datetime) -> int:
    """Calculate days until a datetime."""
    now = datetime.now(get_timezone())
    if dt.tzinfo is None:
        dt = get_timezone().localize(dt)
    delta = dt.date() - now.date()
    return delta.days


def parse_username(text: str) -> Optional[str]:
    """Parse Telegram username from text (with or without @)."""
    text = text.strip()
    if text.startswith("@"):
        text = text[1:]
    
    # Validate username format
    if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', text):
        return text.lower()
    return None


def parse_email(text: str) -> Optional[str]:
    """Parse and validate email address."""
    text = text.strip()
    # Basic email validation
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', text):
        return text.lower()
    return None


def format_hire_card(hire: Hire) -> str:
    """Format hire data as a card message."""
    status_emoji = {
        HireStatus.CREATED: "🆕",
        HireStatus.IN_PROGRESS: "🔄",
        HireStatus.READY_FOR_DAY1: "✅",
        HireStatus.COMPLETED: "🏁",
    }
    
    leader_emoji = "✅" if hire.leader_status == LeaderStatus.ACKNOWLEDGED else "⏳"
    legal_emoji = "✅" if hire.legal_status == LegalStatus.DOCS_SENT else "⏳"
    devops_emoji = "✅" if hire.devops_status == DevOpsStatus.ACCESS_GRANTED else "⏳"
    
    # Format checklist
    checklist = hire.access_checklist or {}
    checklist_items = []
    checklist_names = {
        "email": "📧 Email",
        "github": "💻 GitHub",
        "jira": "📋 Jira",
        "vpn": "🔒 VPN",
        "slack": "💬 Slack/Telegram",
        "cloud": "☁️ Облако",
        "prod": "🚀 Prod/Stage",
        "other": "📝 Другое",
    }
    for key, name in checklist_names.items():
        if checklist.get(key):
            checklist_items.append(name)
    
    checklist_str = ", ".join(checklist_items) if checklist_items else "Не указан"
    
    # Calculate days until start
    days = days_until(hire.start_date)
    if days > 0:
        days_str = f"через {days} дн."
    elif days == 0:
        days_str = "сегодня!"
    else:
        days_str = f"{abs(days)} дн. назад"
    
    card = f"""
🎯 <b>New Hire #{hire.hire_id}</b>

<b>👤 ФИО:</b> {hire.full_name}
<b>📅 Дата выхода:</b> {format_date(hire.start_date)} ({days_str})
<b>💼 Роль:</b> {hire.role}

<b>👥 Ответственные:</b>
├ 👔 Leader: @{hire.leader_username} {leader_emoji}
├ ⚖️ Legal: @{hire.legal_username} {legal_emoji}
└ 🔧 DevOps: @{hire.devops_username} {devops_emoji}

<b>📧 Почта для документов:</b> {hire.docs_email}
<b>📋 Чеклист доступов:</b> {checklist_str}
"""
    
    if hire.notes:
        card += f"\n<b>📝 Примечания:</b>\n{hire.notes}\n"
    
    card += f"""
<b>📊 Статус:</b> {status_emoji.get(hire.status, '')} {hire.status.value}
<b>📅 Создано:</b> {format_datetime(hire.created_at)}
"""
    
    return card.strip()


def format_status_details(hire: Hire) -> str:
    """Format detailed status for a hire."""
    status_emoji = {
        HireStatus.CREATED: "🆕",
        HireStatus.IN_PROGRESS: "🔄",
        HireStatus.READY_FOR_DAY1: "✅",
        HireStatus.COMPLETED: "🏁",
    }
    
    leader_emoji = "✅" if hire.leader_status == LeaderStatus.ACKNOWLEDGED else "⏳"
    legal_emoji = "✅" if hire.legal_status == LegalStatus.DOCS_SENT else "⏳"
    devops_emoji = "✅" if hire.devops_status == DevOpsStatus.ACCESS_GRANTED else "⏳"
    
    days = days_until(hire.start_date)
    if days > 0:
        days_str = f"через {days} дн."
    elif days == 0:
        days_str = "сегодня!"
    else:
        days_str = f"{abs(days)} дн. назад"
    
    text = f"""
📊 <b>Детальный статус #{hire.hire_id}</b>

<b>Общий статус:</b> {status_emoji.get(hire.status, '')} {hire.status.value}

<b>Детали по ролям:</b>
├ 👔 Leader: {leader_emoji} {hire.leader_status.value}
├ ⚖️ Legal: {legal_emoji} {hire.legal_status.value}
└ 🔧 DevOps: {devops_emoji} {hire.devops_status.value}

<b>📅 Дата выхода:</b> {format_date(hire.start_date)} ({days_str})

<b>⏰ Напоминания:</b>
├ Legal: {"✅ Отправлено" if hire.legal_reminded else "⏳ Ожидает"}
├ DevOps: {"✅ Отправлено" if hire.devops_reminded else "⏳ Ожидает"}
└ Эскалация: {"⚠️ Да" if hire.escalated else "✅ Нет"}

<b>🕐 Последнее обновление:</b> {format_datetime(hire.updated_at)}
"""
    
    return text.strip()


def format_hire_list_item(hire: Hire) -> str:
    """Format a single hire for list view."""
    status_emoji = {
        HireStatus.CREATED: "🆕",
        HireStatus.IN_PROGRESS: "🔄",
        HireStatus.READY_FOR_DAY1: "✅",
        HireStatus.COMPLETED: "🏁",
    }
    
    days = days_until(hire.start_date)
    if days > 0:
        days_str = f"+{days}д"
    elif days == 0:
        days_str = "сег"
    else:
        days_str = f"{days}д"
    
    leader = "✅" if hire.leader_status == LeaderStatus.ACKNOWLEDGED else "⏳"
    legal = "✅" if hire.legal_status == LegalStatus.DOCS_SENT else "⏳"
    devops = "✅" if hire.devops_status == DevOpsStatus.ACCESS_GRANTED else "⏳"
    
    return (
        f"{status_emoji.get(hire.status, '')} <b>#{hire.hire_id}</b> "
        f"{hire.full_name} ({hire.role})\n"
        f"   📅 {format_date(hire.start_date)} ({days_str}) | "
        f"👔{leader} ⚖️{legal} 🔧{devops}"
    )
