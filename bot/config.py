"""
Configuration module for Onboarding Bot.
Loads environment variables and provides settings.
"""
import os
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Bot configuration
    BOT_TOKEN: str = Field(..., description="Telegram Bot Token")
    
    # Database
    DB_URL: str = Field(
        default="sqlite+aiosqlite:///./onboarding.db",
        description="Database connection URL"
    )
    
    # Default assignees
    DEFAULT_LEGAL_USERNAME: str = Field(
        default="",
        description="Default legal team Telegram username (without @)"
    )
    DEFAULT_DEVOPS_USERNAME: str = Field(
        default="",
        description="Default DevOps Telegram username (without @)"
    )
    
    # Chat configuration
    ONBOARDING_CHAT_ID: int = Field(
        default=0,
        description="ID of the onboarding chat/group"
    )
    
    # Access control
    ALLOWED_CREATORS: str = Field(
        default="",
        description="Comma-separated list of Telegram user IDs allowed to create hires"
    )
    ADMIN_IDS: str = Field(
        default="",
        description="Comma-separated list of admin Telegram user IDs"
    )
    
    # Timezone
    TIMEZONE: str = Field(
        default="Europe/London",
        description="Timezone for date/time operations"
    )
    
    # Reminder settings
    LEGAL_REMINDER_DAYS: int = Field(
        default=3,
        description="Days before start_date to remind legal"
    )
    DEVOPS_REMINDER_DAYS: int = Field(
        default=1,
        description="Days before start_date to remind devops"
    )
    ESCALATION_HOURS: int = Field(
        default=24,
        description="Hours after deadline to escalate"
    )
    SCHEDULER_INTERVAL_MINUTES: int = Field(
        default=30,
        description="How often to check reminders (in minutes)"
    )
    
    @property
    def allowed_creators_list(self) -> List[int]:
        """Parse ALLOWED_CREATORS into list of integers."""
        if not self.ALLOWED_CREATORS:
            return []
        return [int(x.strip()) for x in self.ALLOWED_CREATORS.split(",") if x.strip()]
    
    @property
    def admin_ids_list(self) -> List[int]:
        """Parse ADMIN_IDS into list of integers."""
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


# Global settings instance
settings = Settings()
