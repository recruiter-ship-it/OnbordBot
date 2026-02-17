"""
Handler for inline button callbacks.
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database import get_session
from bot.database.models import LeaderStatus, LegalStatus, DevOpsStatus
from bot.services.hire_service import HireService
from bot.keyboards.inline import (
    get_hire_card_keyboard,
    get_status_keyboard,
    CALLBACK_LEADER_ACK,
    CALLBACK_DOCS_SENT,
    CALLBACK_ACCESS_GRANTED,
    CALLBACK_COMPLETE,
    CALLBACK_REOPEN,
    CALLBACK_SHOW_STATUS,
    CALLBACK_ADD_NOTE,
)
from bot.utils.formatting import format_hire_card, format_status_details
from bot.middlewares.access import is_creator_or_admin, is_admin
from bot.logger import get_logger

logger = get_logger(__name__)

router = Router()


class NoteState(StatesGroup):
    """State for adding notes."""
    waiting_for_note = State()


@router.callback_query(F.data.startswith(CALLBACK_LEADER_ACK))
async def leader_acknowledge(callback: CallbackQuery, bot: Bot):
    """Handle leader acknowledgment."""
    hire_id = callback.data[len(CALLBACK_LEADER_ACK):]
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        # Check if this is the assigned leader (by username or ID)
        is_leader = (
            user_id == hire.leader_id or
            username.lower() == hire.leader_username.lower()
        )
        
        if not is_leader and not is_admin(user_id):
            await callback.answer(
                "❌ Недостаточно прав. Только назначенный лидер может подтвердить.",
                show_alert=True
            )
            return
        
        if hire.leader_status == LeaderStatus.ACKNOWLEDGED:
            await callback.answer("✅ Уже подтверждено", show_alert=True)
            return
        
        # Update status
        hire = await hire_service.update_leader_status(
            hire_id=hire_id,
            status=LeaderStatus.ACKNOWLEDGED,
            actor_id=user_id,
            actor_username=username,
        )
        
        # Update message
        await _update_card_message(bot, hire, user_id)
        
        await callback.answer("✅ Статус обновлён: Leader acknowledged")
        logger.info("Leader acknowledged", hire_id=hire_id, user_id=user_id)


@router.callback_query(F.data.startswith(CALLBACK_DOCS_SENT))
async def docs_sent(callback: CallbackQuery, bot: Bot):
    """Handle docs sent action."""
    hire_id = callback.data[len(CALLBACK_DOCS_SENT):]
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        # Check if this is the assigned legal (by username or ID)
        is_legal = (
            user_id == hire.legal_id or
            username.lower() == hire.legal_username.lower()
        )
        
        if not is_legal and not is_admin(user_id):
            await callback.answer(
                "❌ Недостаточно прав. Только назначенный юрист может отправить документы.",
                show_alert=True
            )
            return
        
        if hire.legal_status == LegalStatus.DOCS_SENT:
            await callback.answer("✅ Документы уже отправлены", show_alert=True)
            return
        
        # Update status
        hire = await hire_service.update_legal_status(
            hire_id=hire_id,
            status=LegalStatus.DOCS_SENT,
            actor_id=user_id,
            actor_username=username,
        )
        
        # Update message
        await _update_card_message(bot, hire, user_id)
        
        await callback.answer("✅ Статус обновлён: Docs sent")
        logger.info("Docs sent", hire_id=hire_id, user_id=user_id)


@router.callback_query(F.data.startswith(CALLBACK_ACCESS_GRANTED))
async def access_granted(callback: CallbackQuery, bot: Bot):
    """Handle access granted action."""
    hire_id = callback.data[len(CALLBACK_ACCESS_GRANTED):]
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        # Check if this is the assigned devops (by username or ID)
        is_devops = (
            user_id == hire.devops_id or
            username.lower() == hire.devops_username.lower()
        )
        
        if not is_devops and not is_admin(user_id):
            await callback.answer(
                "❌ Недостаточно прав. Только назначенный DevOps может выдать доступы.",
                show_alert=True
            )
            return
        
        if hire.devops_status == DevOpsStatus.ACCESS_GRANTED:
            await callback.answer("✅ Доступы уже выданы", show_alert=True)
            return
        
        # Update status
        hire = await hire_service.update_devops_status(
            hire_id=hire_id,
            status=DevOpsStatus.ACCESS_GRANTED,
            actor_id=user_id,
            actor_username=username,
        )
        
        # Update message
        await _update_card_message(bot, hire, user_id)
        
        await callback.answer("✅ Статус обновлён: Access granted")
        logger.info("Access granted", hire_id=hire_id, user_id=user_id)


@router.callback_query(F.data.startswith(CALLBACK_COMPLETE))
async def mark_complete(callback: CallbackQuery, bot: Bot):
    """Mark hire as completed."""
    hire_id = callback.data[len(CALLBACK_COMPLETE):]
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        # Only creator or admin can mark as completed
        if not is_creator_or_admin(user_id):
            await callback.answer(
                "❌ Недостаточно прав. Только рекрутер или админ может завершить.",
                show_alert=True
            )
            return
        
        # Update status
        hire = await hire_service.mark_completed(
            hire_id=hire_id,
            actor_id=user_id,
            actor_username=username,
        )
        
        # Update message
        await _update_card_message(bot, hire, user_id)
        
        await callback.answer("✅ Карточка завершена!")
        logger.info("Hire completed", hire_id=hire_id, user_id=user_id)


@router.callback_query(F.data.startswith(CALLBACK_REOPEN))
async def reopen_hire(callback: CallbackQuery, bot: Bot):
    """Reopen a completed hire."""
    hire_id = callback.data[len(CALLBACK_REOPEN):]
    user_id = callback.from_user.id
    username = callback.from_user.username or ""
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        # Only creator or admin can reopen
        if not is_creator_or_admin(user_id):
            await callback.answer(
                "❌ Недостаточно прав. Только рекрутер или админ может переоткрыть.",
                show_alert=True
            )
            return
        
        # Update status
        hire = await hire_service.reopen(
            hire_id=hire_id,
            actor_id=user_id,
            actor_username=username,
        )
        
        # Update message
        await _update_card_message(bot, hire, user_id)
        
        await callback.answer("🔄 Карточка переоткрыта")
        logger.info("Hire reopened", hire_id=hire_id, user_id=user_id)


@router.callback_query(F.data.startswith(CALLBACK_SHOW_STATUS))
async def show_status(callback: CallbackQuery, bot: Bot):
    """Show detailed status."""
    hire_id = callback.data[len(CALLBACK_SHOW_STATUS):]
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        status_text = format_status_details(hire)
        
        await callback.message.edit_text(
            status_text,
            parse_mode="HTML",
            reply_markup=get_status_keyboard(hire_id),
        )
        
        await callback.answer()


@router.callback_query(F.data.startswith("back_to_card:"))
async def back_to_card(callback: CallbackQuery, bot: Bot):
    """Go back to card view from status."""
    hire_id = callback.data[len("back_to_card:"):]
    user_id = callback.from_user.id
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена", show_alert=True)
            return
        
        await _update_card_message(bot, hire, user_id, message=callback.message)
        await callback.answer()


@router.callback_query(F.data.startswith(CALLBACK_ADD_NOTE))
async def add_note_start(callback: CallbackQuery, state: FSMContext):
    """Start note addition process."""
    hire_id = callback.data[len(CALLBACK_ADD_NOTE):]
    user_id = callback.from_user.id
    
    if not is_creator_or_admin(user_id):
        await callback.answer(
            "❌ Недостаточно прав.",
            show_alert=True
        )
        return
    
    await state.update_data(hire_id=hire_id, message_id=callback.message.message_id)
    
    await callback.message.answer(
        "📝 Введите текст заметки:",
    )
    
    await state.set_state(NoteState.waiting_for_note)
    await callback.answer()


@router.message(NoteState.waiting_for_note)
async def add_note_process(message: Message, state: FSMContext, bot: Bot):
    """Process note addition."""
    data = await state.get_data()
    hire_id = data.get("hire_id")
    user_id = message.from_user.id
    username = message.from_user.username or ""
    
    note = message.text.strip()
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.add_note(
            hire_id=hire_id,
            note=note,
            actor_id=user_id,
            actor_username=username,
        )
        
        if hire:
            await _update_card_message(bot, hire, user_id)
            await message.answer("✅ Заметка добавлена")
    
    await state.clear()


async def _update_card_message(
    bot: Bot, 
    hire, 
    user_id: int,
    message: Message = None
) -> None:
    """Update the hire card message in the chat."""
    card = format_hire_card(hire)
    
    is_creator = user_id == hire.creator_id
    is_adm = is_admin(user_id)
    
    keyboard = get_hire_card_keyboard(
        hire_id=hire.hire_id,
        leader_status=hire.leader_status,
        legal_status=hire.legal_status,
        devops_status=hire.devops_status,
        overall_status=hire.status,
        is_creator=is_creator,
        is_admin=is_adm,
    )
    
    try:
        if message:
            await message.edit_text(
                card,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        elif hire.message_id:
            await bot.edit_message_text(
                chat_id=hire.chat_id,
                message_id=hire.message_id,
                text=card,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
    except Exception as e:
        logger.warning("Failed to update message", error=str(e))
