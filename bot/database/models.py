"""
Database models for Onboarding Bot.
Uses SQLAlchemy with async support.
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import (
    String, Integer, DateTime, Text, Boolean, JSON, ForeignKey, Enum as SQLEnum
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class HireStatus(str, PyEnum):
    """Overall hire status."""
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    READY_FOR_DAY1 = "READY_FOR_DAY1"
    COMPLETED = "COMPLETED"


class LeaderStatus(str, PyEnum):
    """Leader acknowledgement status."""
    PENDING = "PENDING"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class LegalStatus(str, PyEnum):
    """Legal documents status."""
    PENDING = "PENDING"
    DOCS_SENT = "DOCS_SENT"


class DevOpsStatus(str, PyEnum):
    """DevOps access status."""
    PENDING = "PENDING"
    ACCESS_GRANTED = "ACCESS_GRANTED"


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Hire(Base):
    """Model representing a new hire."""
    __tablename__ = "hires"
    
    hire_id: Mapped[str] = mapped_column(String(10), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    role: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Telegram IDs (can be None if username not resolved)
    leader_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    leader_username: Mapped[str] = mapped_column(String(100), nullable=False)
    
    legal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    legal_username: Mapped[str] = mapped_column(String(100), nullable=False)
    
    devops_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    devops_username: Mapped[str] = mapped_column(String(100), nullable=False)
    
    docs_email: Mapped[str] = mapped_column(String(255), nullable=False)
    access_checklist: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Statuses
    status: Mapped[HireStatus] = mapped_column(
        SQLEnum(HireStatus), 
        nullable=False, 
        default=HireStatus.CREATED
    )
    leader_status: Mapped[LeaderStatus] = mapped_column(
        SQLEnum(LeaderStatus), 
        nullable=False, 
        default=LeaderStatus.PENDING
    )
    legal_status: Mapped[LegalStatus] = mapped_column(
        SQLEnum(LegalStatus), 
        nullable=False, 
        default=LegalStatus.PENDING
    )
    devops_status: Mapped[DevOpsStatus] = mapped_column(
        SQLEnum(DevOpsStatus), 
        nullable=False, 
        default=DevOpsStatus.PENDING
    )
    
    # Telegram message info
    chat_id: Mapped[int] = mapped_column(Integer, nullable=False)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Creator info
    creator_id: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Reminder flags
    legal_reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    devops_reminded: Mapped[bool] = mapped_column(Boolean, default=False)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        server_default=func.now(),
        onupdate=func.now()
    )
    
    # Relationships
    history: Mapped[List["StatusHistory"]] = relationship(
        "StatusHistory", 
        back_populates="hire",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Hire(hire_id={self.hire_id}, full_name={self.full_name})>"


class StatusHistory(Base):
    """Model for tracking status changes."""
    __tablename__ = "status_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hire_id: Mapped[str] = mapped_column(String(10), ForeignKey("hires.hire_id"), nullable=False)
    actor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        server_default=func.now()
    )
    
    # Relationship
    hire: Mapped["Hire"] = relationship("Hire", back_populates="history")
    
    def __repr__(self) -> str:
        return f"<StatusHistory(hire_id={self.hire_id}, action={self.action})>"


class DefaultSettings(Base):
    """Model for storing default settings."""
    __tablename__ = "default_settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        server_default=func.now(),
        onupdate=func.now()
    )
    
    def __repr__(self) -> str:
        return f"<DefaultSettings(key={self.key}, value={self.value})>"
