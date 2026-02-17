"""
Utility functions for the Onboarding Bot.
"""
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple
import pytz
from bot.config import settings
from bot.logger import get_logger

logger = get_logger(__name__)

# Timezone
TZ = pytz.timezone(settings.TIMEZONE)


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse date string in YYYY-MM-DD format.
    Returns datetime in configured timezone (Europe/London).
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Set to beginning of work day (9 AM) in configured timezone
        dt = TZ.localize(dt.replace(hour=9, minute=0, second=0, microsecond=0))
        return dt
    except ValueError:
        return None


def format_date(dt: datetime) -> str:
    """Format datetime for display."""
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    return dt.strftime("%d.%m.%Y")


def format_datetime(dt: datetime) -> str:
    """Format datetime with time for display."""
    if dt.tzinfo is None:
        dt = TZ.localize(dt)
    return dt.strftime("%d.%m.%Y %H:%M")


def get_now() -> datetime:
    """Get current datetime in configured timezone."""
    return datetime.now(TZ)


def days_until(dt: datetime) -> int:
    """Calculate days until a given datetime."""
    now = get_now()
    # Convert to date for comparison
    delta = dt.date() - now.date()
    return delta.days


def is_overdue(dt: datetime, hours: int = 24) -> Tuple[bool, int]:
    """
    Check if a datetime is overdue by more than specified hours.
    Returns (is_overdue, hours_overdue).
    """
    now = get_now()
    threshold = dt + timedelta(hours=hours)
    
    if now > threshold:
        hours_overdue = int((now - threshold).total_seconds() / 3600)
        return True, hours_overdue
    
    return False, 0


def parse_username(username: str) -> Optional[str]:
    """
    Parse Telegram username, removing @ if present.
    Returns lowercase username without @.
    """
    if not username:
        return None
    
    username = username.strip().lstrip("@").lower()
    
    # Validate username format
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{4,31}$", username):
        return None
    
    return username


def validate_email(email: str) -> bool:
    """Validate email format."""
    if not email:
        return False
    
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email.strip()))


def format_checklist(checklist: dict) -> str:
    """Format checklist dict for display."""
    if not checklist:
        return "Не указан"
    
    items = []
    for key, value in checklist.items():
        if value and value is True:
            items.append(f"• {key}")
        elif value and isinstance(value, str):
            items.append(f"• {key}: {value}")
    
    return "\n".join(items) if items else "Не указан"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."

