"""
Service layer for Hire operations.
"""
import random
import string
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import (
    Hire,
    StatusHistory,
    DefaultSettings,
    HireStatus,
    LeaderStatus,
    LegalStatus,
    DevOpsStatus,
)
from bot.logger import get_logger

logger = get_logger(__name__)


def generate_hire_id() -> str:
    """Generate a unique 4-character hire ID."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))


class HireService:
    """Service class for Hire operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create_hire(
        self,
        full_name: str,
        start_date: datetime,
        role: str,
        leader_username: str,
        legal_username: str,
        devops_username: str,
        docs_email: str,
        access_checklist: dict,
        chat_id: int,
        creator_id: int,
        notes: Optional[str] = None,
        leader_id: Optional[int] = None,
        legal_id: Optional[int] = None,
        devops_id: Optional[int] = None,
    ) -> Hire:
        """Create a new hire record."""
        # Generate unique hire_id
        while True:
            hire_id = generate_hire_id()
            existing = await self.get_hire(hire_id)
            if not existing:
                break
        
        hire = Hire(
            hire_id=hire_id,
            full_name=full_name,
            start_date=start_date,
            role=role,
            leader_username=leader_username,
            leader_id=leader_id,
            legal_username=legal_username,
            legal_id=legal_id,
            devops_username=devops_username,
            devops_id=devops_id,
            docs_email=docs_email,
            access_checklist=access_checklist,
            notes=notes,
            chat_id=chat_id,
            creator_id=creator_id,
            status=HireStatus.CREATED,
            leader_status=LeaderStatus.PENDING,
            legal_status=LegalStatus.PENDING,
            devops_status=DevOpsStatus.PENDING,
        )
        
        self.session.add(hire)
        
        # Add history entry
        history = StatusHistory(
            hire_id=hire_id,
            actor_id=creator_id,
            action="CREATED",
            details=f"Created hire record for {full_name}",
        )
        self.session.add(history)
        
        await self.session.commit()
        await self.session.refresh(hire)
        
        logger.info(
            "Hire created",
            hire_id=hire_id,
            full_name=full_name,
            creator_id=creator_id,
        )
        
        return hire
    
    async def get_hire(self, hire_id: str) -> Optional[Hire]:
        """Get a hire by ID."""
        result = await self.session.execute(
            select(Hire).where(Hire.hire_id == hire_id)
        )
        return result.scalar_one_or_none()
    
    async def get_hires_by_status(
        self, 
        statuses: Optional[List[HireStatus]] = None,
        exclude_completed: bool = True,
    ) -> List[Hire]:
        """Get hires filtered by status."""
        query = select(Hire)
        
        if exclude_completed:
            query = query.where(HireStatus != HireStatus.COMPLETED)
        
        if statuses:
            query = query.where(Hire.status.in_(statuses))
        
        query = query.order_by(Hire.start_date.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def get_open_hires(self) -> List[Hire]:
        """Get all open (non-completed) hires."""
        return await self.get_hires_by_status(exclude_completed=True)
    
    async def get_hires_needing_reminders(self) -> List[Hire]:
        """Get hires that need reminders."""
        now = datetime.now()
        
        result = await self.session.execute(
            select(Hire).where(
                and_(
                    Hire.status != HireStatus.COMPLETED,
                    or_(
                        # Legal reminder needed
                        and_(
                            Hire.legal_status == LegalStatus.PENDING,
                            Hire.legal_reminded == False,
                        ),
                        # DevOps reminder needed
                        and_(
                            Hire.devops_status == DevOpsStatus.PENDING,
                            Hire.devops_reminded == False,
                        ),
                        # Escalation needed
                        Hire.escalated == False,
                    ),
                )
            )
        )
        return list(result.scalars().all())
    
    async def update_leader_status(
        self, 
        hire_id: str, 
        status: LeaderStatus,
        actor_id: int,
        actor_username: Optional[str] = None,
    ) -> Optional[Hire]:
        """Update leader status."""
        hire = await self.get_hire(hire_id)
        if not hire:
            return None
        
        old_status = hire.leader_status
        hire.leader_status = status
        
        # Add history entry
        history = StatusHistory(
            hire_id=hire_id,
            actor_id=actor_id,
            actor_username=actor_username,
            action="LEADER_STATUS_CHANGED",
            details=f"Leader status: {old_status.value} -> {status.value}",
        )
        self.session.add(history)
        
        # Update overall status
        await self._update_overall_status(hire)
        
        await self.session.commit()
        await self.session.refresh(hire)
        
        logger.info(
            "Leader status updated",
            hire_id=hire_id,
            old_status=old_status.value,
            new_status=status.value,
            actor_id=actor_id,
        )
        
        return hire
    
    async def update_legal_status(
        self, 
        hire_id: str, 
        status: LegalStatus,
        actor_id: int,
        actor_username: Optional[str] = None,
    ) -> Optional[Hire]:
        """Update legal status."""
        hire = await self.get_hire(hire_id)
        if not hire:
            return None
        
        old_status = hire.legal_status
        hire.legal_status = status
        
        # Add history entry
        history = StatusHistory(
            hire_id=hire_id,
            actor_id=actor_id,
            actor_username=actor_username,
            action="LEGAL_STATUS_CHANGED",
            details=f"Legal status: {old_status.value} -> {status.value}",
        )
        self.session.add(history)
        
        # Update overall status
        await self._update_overall_status(hire)
        
        await self.session.commit()
        await self.session.refresh(hire)
        
        logger.info(
            "Legal status updated",
            hire_id=hire_id,
            old_status=old_status.value,
            new_status=status.value,
            actor_id=actor_id,
        )
        
        return hire
    
    async def update_devops_status(
        self, 
        hire_id: str, 
        status: DevOpsStatus,
        actor_id: int,
        actor_username: Optional[str] = None,
    ) -> Optional[Hire]:
        """Update DevOps status."""
        hire = await self.get_hire(hire_id)
        if not hire:
            return None
        
        old_status = hire.devops_status
        hire.devops_status = status
        
        # Add history entry
        history = StatusHistory(
            hire_id=hire_id,
            actor_id=actor_id,
            actor_username=actor_username,
            action="DEVOPS_STATUS_CHANGED",
            details=f"DevOps status: {old_status.value} -> {status.value}",
        )
        self.session.add(history)
        
        # Update overall status
        await self._update_overall_status(hire)
        
        await self.session.commit()
        await self.session.refresh(hire)
        
        logger.info(
            "DevOps status updated",
            hire_id=hire_id,
            old_status=old_status.value,
            new_status=status.value,
            actor_id=actor_id,
        )
        
        return hire
    
    async def update_message_id(
        self, 
        hire_id: str, 
        message_id: int
    ) -> Optional[Hire]:
        """Update the Telegram message ID for a hire."""
        hire = await self.get_hire(hire_id)
        if not hire:
            return None
        
        hire.message_id = message_id
        await self.session.commit()
        return hire
    
    async def mark_completed(
        self, 
        hire_id: str,
        actor_id: int,
        actor_username: Optional[str] = None,
    ) -> Optional[Hire]:
        """Mark a hire as completed."""
        hire = await self.get_hire(hire_id)
        if not hire:
            return None
        
        old_status = hire.status
        hire.status = HireStatus.COMPLETED
        
        # Add history entry
        history = StatusHistory(
            hire_id=hire_id,
            actor_id=actor_id,
            actor_username=actor_username,
            action="COMPLETED",
            details=f"Marked as completed",
        )
        self.session.add(history)
        
        await self.session.commit()
        await self.session.refresh(hire)
        
        logger.info(
            "Hire completed",
            hire_id=hire_id,
            actor_id=actor_id,
        )
        
        return hire
    
    async def reopen(
        self, 
        hire_id: str,
        actor_id: int,
        actor_username: Optional[str] = None,
    ) -> Optional[Hire]:
        """Reopen a completed hire."""
        hire = await self.get_hire(hire_id)
        if not hire:
            return None
        
        old_status = hire.status
        hire.status = HireStatus.IN_PROGRESS
        
        # Add history entry
        history = StatusHistory(
            hire_id=hire_id,
            actor_id=actor_id,
            actor_username=actor_username,
            action="REOPENED",
            details=f"Reopened from {old_status.value}",
        )
        self.session.add(history)
        
        await self.session.commit()
        await self.session.refresh(hire)
        
        logger.info(
            "Hire reopened",
            hire_id=hire_id,
            actor_id=actor_id,
        )
        
        return hire
    
    async def add_note(
        self, 
        hire_id: str,
        note: str,
        actor_id: int,
        actor_username: Optional[str] = None,
    ) -> Optional[Hire]:
        """Add a note to a hire."""
        hire = await self.get_hire(hire_id)
        if not hire:
            return None
        
        existing_notes = hire.notes or ""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_note = f"\n[{timestamp}] {note}"
        hire.notes = existing_notes + new_note
        
        # Add history entry
        history = StatusHistory(
            hire_id=hire_id,
            actor_id=actor_id,
            actor_username=actor_username,
            action="NOTE_ADDED",
            details=note,
        )
        self.session.add(history)
        
        await self.session.commit()
        await self.session.refresh(hire)
        
        logger.info(
            "Note added",
            hire_id=hire_id,
            actor_id=actor_id,
        )
        
        return hire
    
    async def mark_legal_reminded(self, hire_id: str) -> None:
        """Mark that legal has been reminded."""
        hire = await self.get_hire(hire_id)
        if hire:
            hire.legal_reminded = True
            await self.session.commit()
    
    async def mark_devops_reminded(self, hire_id: str) -> None:
        """Mark that devops has been reminded."""
        hire = await self.get_hire(hire_id)
        if hire:
            hire.devops_reminded = True
            await self.session.commit()
    
    async def mark_escalated(self, hire_id: str) -> None:
        """Mark that the hire has been escalated."""
        hire = await self.get_hire(hire_id)
        if hire:
            hire.escalated = True
            await self.session.commit()
    
    async def _update_overall_status(self, hire: Hire) -> None:
        """Update overall status based on individual statuses."""
        if hire.status == HireStatus.COMPLETED:
            return
        
        # Check if ready for day 1
        if (hire.leader_status == LeaderStatus.ACKNOWLEDGED and
            hire.legal_status == LegalStatus.DOCS_SENT and
            hire.devops_status == DevOpsStatus.ACCESS_GRANTED):
            hire.status = HireStatus.READY_FOR_DAY1
        # Check if in progress
        elif (hire.leader_status != LeaderStatus.PENDING or
              hire.legal_status != LegalStatus.PENDING or
              hire.devops_status != DevOpsStatus.PENDING):
            hire.status = HireStatus.IN_PROGRESS
    
    async def get_history(self, hire_id: str) -> List[StatusHistory]:
        """Get status history for a hire."""
        result = await self.session.execute(
            select(StatusHistory)
            .where(StatusHistory.hire_id == hire_id)
            .order_by(StatusHistory.ts.asc())
        )
        return list(result.scalars().all())


class SettingsService:
    """Service for default settings management."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_setting(self, key: str) -> Optional[str]:
        """Get a setting value."""
        result = await self.session.execute(
            select(DefaultSettings).where(DefaultSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        return setting.value if setting else None
    
    async def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        result = await self.session.execute(
            select(DefaultSettings).where(DefaultSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = value
        else:
            setting = DefaultSettings(key=key, value=value)
            self.session.add(setting)
        
        await self.session.commit()
        logger.info("Setting updated", key=key, value=value)
    
    async def get_default_legal(self) -> Optional[str]:
        """Get default legal username."""
        return await self.get_setting("default_legal")
    
    async def get_default_devops(self) -> Optional[str]:
        """Get default devops username."""
        return await self.get_setting("default_devops")
    
    async def set_default_legal(self, username: str) -> None:
        """Set default legal username."""
        await self.set_setting("default_legal", username)
    
    async def set_default_devops(self, username: str) -> None:
        """Set default devops username."""
        await self.set_setting("default_devops", username)
