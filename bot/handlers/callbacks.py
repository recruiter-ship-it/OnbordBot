"""
Handler for inline button callbacks (status updates, etc.).
"""
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database import get_session
from bot.database.models import (
    Hire,
    HireStatus,
    LeaderStatus,
    LegalStatus,
    DevOpsStatus,
)
from bot.services.hire_service import HireService
from bot.keyboards.inline import (
    get_hire_card_keyboard,
    CALLBACK_LEADER_ACK,
    CALLBACK_DOCS_SENT,
    CALLBACK_ACCESS_GRANTED,
    CALLBACK_COMPLETE,
    CALLBACK_REOPEN,
    CALLBACK_SHOW_STATUS,
    CALLBACK_ADD_NOTE,
)
from bot.handlers.newhire import format_hire_card
from bot.utils.date_utils import format_date, format_datetime
from bot.logger import get_logger

logger = get_logger(__name__)

router = Router()


# --- Helper Functions ---

def is_user_authorized_for_action(
    callback: CallbackQuery,
    hire: Hire,
    action: str,
) -> bool:
    """Check if user is authorized to perform the action."""
    user_id = callback.from_user.id
    username = callback.from_user.username.lower() if callback.from_user.username else ""
    
    is_creator = user_id == hire.creator_id
    is_admin = user_id in settings.admin_ids_list
    
    if action == "leader_ack":
        # Only the assigned leader can acknowledge
        return (
            user_id == hire.leader_id or
            username == hire.leader_username.lower() or
            is_creator or
            is_admin
        )
    
    elif action == "docs_sent":
        # Only the assigned legal can mark docs sent
        return (
            user_id == hire.legal_id or
            username == hire.legal_username.lower() or
            is_creator or
            is_admin
        )
    
    elif action == "access_granted":
        # Only the assigned devops can grant access
        return (
            user_id == hire.devops_id or
            username == hire.devops_username.lower() or
            is_creator or
            is_admin
        )
    
    elif action in ["complete", "reopen", "add_note"]:
        # Only creator or admin can complete/reopen/add notes
        return is_creator or is_admin
    
    elif action == "show_status":
        # Everyone can view status
        return True
    
    return False


async def update_card_message(
    bot: Bot,
    hire: Hire,
    is_creator: bool = False,
    is_admin: bool = False,
):
    """Update the hire card message in the group chat."""
    try:
        card_text = format_hire_card(hire)
        keyboard = get_hire_card_keyboard(
            hire_id=hire.hire_id,
            leader_status=hire.leader_status,
            legal_status=hire.legal_status,
            devops_status=hire.devops_status,
            overall_status=hire.status,
            is_creator=is_creator,
            is_admin=is_admin,
        )
        
        await bot.edit_message_text(
            chat_id=hire.chat_id,
            message_id=hire.message_id,
            text=card_text,
            parse_mode="HTML",
            reply_markup=keyboard,
        )
    except TelegramBadRequest as e:
        logger.warning(
            "Failed to update card message",
            hire_id=hire.hire_id,
            error=str(e),
        )


# --- Leader Acknowledge Handler ---

@router.callback_query(F.data.startswith(CALLBACK_LEADER_ACK))
async def leader_acknowledge(callback: CallbackQuery, bot: Bot):
    """Handle leader acknowledge button."""
    hire_id = callback.data[len(CALLBACK_LEADER_ACK):]
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена!", show_alert=True)
            return
        
        if not is_user_authorized_for_action(callback, hire, "leader_ack"):
            await callback.answer(
                "⛔ Недостаточно прав. Только назначенный лидер может подтвердить.",
                show_alert=True,
            )
            return
        
        if hire.leader_status == LeaderStatus.ACKNOWLEDGED:
            await callback.answer("✅ Уже подтверждено!", show_alert=True)
            return
        
        # Update status
        await hire_service.update_leader_status(
            hire_id=hire_id,
            status=LeaderStatus.ACKNOWLEDGED,
            actor_id=callback.from_user.id,
            actor_username=callback.from_user.username,
        )
        
        # Refresh hire data
        hire = await hire_service.get_hire(hire_id)
        
        # Update card message
        await update_card_message(
            bot,
            hire,
            is_creator=callback.from_user.id == hire.creator_id,
            is_admin=callback.from_user.id in settings.admin_ids_list,
        )
        
        await callback.answer("✅ Статус обновлён: Лидер подтвердил!")
        logger.info(
            "Leader acknowledged",
            hire_id=hire_id,
            actor_id=callback.from_user.id,
        )


# --- Docs Sent Handler ---

@router.callback_query(F.data.startswith(CALLBACK_DOCS_SENT))
async def docs_sent(callback: CallbackQuery, bot: Bot):
    """Handle docs sent button."""
    hire_id = callback.data[len(CALLBACK_DOCS_SENT):]
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена!", show_alert=True)
            return
        
        if not is_user_authorized_for_action(callback, hire, "docs_sent"):
            await callback.answer(
                "⛔ Недостаточно прав. Только юрист может отметить отправку документов.",
                show_alert=True,
            )
            return
        
        if hire.legal_status == LegalStatus.DOCS_SENT:
            await callback.answer("✅ Документы уже отправлены!", show_alert=True)
            return
        
        # Update status
        await hire_service.update_legal_status(
            hire_id=hire_id,
            status=LegalStatus.DOCS_SENT,
            actor_id=callback.from_user.id,
            actor_username=callback.from_user.username,
        )
        
        # Refresh hire data
        hire = await hire_service.get_hire(hire_id)
        
        # Update card message
        await update_card_message(
            bot,
            hire,
            is_creator=callback.from_user.id == hire.creator_id,
            is_admin=callback.from_user.id in settings.admin_ids_list,
        )
        
        await callback.answer("✅ Статус обновлён: Документы отправлены!")
        logger.info(
            "Docs sent",
            hire_id=hire_id,
            actor_id=callback.from_user.id,
        )


# --- Access Granted Handler ---

@router.callback_query(F.data.startswith(CALLBACK_ACCESS_GRANTED))
async def access_granted(callback: CallbackQuery, bot: Bot):
    """Handle access granted button."""
    hire_id = callback.data[len(CALLBACK_ACCESS_GRANTED):]
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена!", show_alert=True)
            return
        
        if not is_user_authorized_for_action(callback, hire, "access_granted"):
            await callback.answer(
                "⛔ Недостаточно прав. Только DevOps может выдать доступы.",
                show_alert=True,
            )
            return
        
        if hire.devops_status == DevOpsStatus.ACCESS_GRANTED:
            await callback.answer("✅ Доступы уже выданы!", show_alert=True)
            return
        
        # Update status
        await hire_service.update_devops_status(
            hire_id=hire_id,
            status=DevOpsStatus.ACCESS_GRANTED,
            actor_id=callback.from_user.id,
            actor_username=callback.from_user.username,
        )
        
        # Refresh hire data
        hire = await hire_service.get_hire(hire_id)
        
        # Update card message
        await update_card_message(
            bot,
            hire,
            is_creator=callback.from_user.id == hire.creator_id,
            is_admin=callback.from_user.id in settings.admin_ids_list,
        )
        
        await callback.answer("✅ Статус обновлён: Доступы выданы!")
        logger.info(
            "Access granted",
            hire_id=hire_id,
            actor_id=callback.from_user.id,
        )


# --- Complete Handler ---

@router.callback_query(F.data.startswith(CALLBACK_COMPLETE))
async def mark_complete(callback: CallbackQuery, bot: Bot):
    """Handle mark complete button."""
    hire_id = callback.data[len(CALLBACK_COMPLETE):]
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена!", show_alert=True)
            return
        
        if not is_user_authorized_for_action(callback, hire, "complete"):
            await callback.answer(
                "⛔ Недостаточно прав. Только создатель или админ может завершить.",
                show_alert=True,
            )
            return
        
        # Update status
        await hire_service.mark_completed(
            hire_id=hire_id,
            actor_id=callback.from_user.id,
            actor_username=callback.from_user.username,
        )
        
        # Refresh hire data
        hire = await hire_service.get_hire(hire_id)
        
        # Update card message
        await update_card_message(
            bot,
            hire,
            is_creator=True,
            is_admin=callback.from_user.id in settings.admin_ids_list,
        )
        
        await callback.answer("✅ Карточка завершена!")
        logger.info(
            "Hire completed",
            hire_id=hire_id,
            actor_id=callback.from_user.id,
        )


# --- Reopen Handler ---

@router.callback_query(F.data.startswith(CALLBACK_REOPEN))
async def reopen_hire(callback: CallbackQuery, bot: Bot):
    """Handle reopen button."""
    hire_id = callback.data[len(CALLBACK_REOPEN):]
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена!", show_alert=True)
            return
        
        if not is_user_authorized_for_action(callback, hire, "reopen"):
            await callback.answer(
                "⛔ Недостаточно прав. Только создатель или админ может переоткрыть.",
                show_alert=True,
            )
            return
        
        # Update status
        await hire_service.reopen(
            hire_id=hire_id,
            actor_id=callback.from_user.id,
            actor_username=callback.from_user.username,
        )
        
        # Refresh hire data
        hire = await hire_service.get_hire(hire_id)
        
        # Update card message
        await update_card_message(
            bot,
            hire,
            is_creator=True,
            is_admin=callback.from_user.id in settings.admin_ids_list,
        )
        
        await callback.answer("🔄 Карточка переоткрыта!")
        logger.info(
            "Hire reopened",
            hire_id=hire_id,
            actor_id=callback.from_user.id,
        )


# --- Show Status Handler ---

@router.callback_query(F.data.startswith(CALLBACK_SHOW_STATUS))
async def show_status(callback: CallbackQuery, bot: Bot):
    """Handle show status button."""
    hire_id = callback.data[len(CALLBACK_SHOW_STATUS):]
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена!", show_alert=True)
            return
        
        # Get history
        history = await hire_service.get_history(hire_id)
        
        # Status icons
        leader_icon = "✅" if hire.leader_status == LeaderStatus.ACKNOWLEDGED else "⏳"
        legal_icon = "✅" if hire.legal_status == LegalStatus.DOCS_SENT else "⏳"
        devops_icon = "✅" if hire.devops_status == DevOpsStatus.ACCESS_GRANTED else "⏳"
        
        status_text = {
            HireStatus.CREATED: "🆕 Создана",
            HireStatus.IN_PROGRESS: "🔄 В процессе",
            HireStatus.READY_FOR_DAY1: "✅ Готов к выходу",
            HireStatus.COMPLETED: "🏁 Завершено",
        }.get(hire.status, hire.status.value)
        
        # Format status message
        status_text_msg = f"""
📊 <b>Подробности #{hire.hire_id}</b>

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ 👤 {hire.full_name}
┃ 📅 {format_date(hire.start_date)} • 💼 {hire.role}
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛

<b>👥 Статусы:</b>
┃ {leader_icon} Лидер: {hire.leader_status.value}
┃ {legal_icon} Юрист: {hire.legal_status.value}
┃ {devops_icon} DevOps: {hire.devops_status.value}

<b>📊 Общий статус:</b> {status_text}

<b>📝 История:</b>
"""
        
        for h in history[-5:]:  # Last 5 entries
            actor = f"@{h.actor_username}" if h.actor_username else f"ID:{h.actor_id}"
            status_text_msg += f"• {format_datetime(h.ts)} — {h.action}\n"
        
        # Send as new message
        try:
            await callback.message.answer(
                status_text_msg,
                parse_mode="HTML",
            )
            await callback.answer()
        except Exception as e:
            logger.warning(
                "Failed to send status",
                hire_id=hire_id,
                error=str(e),
            )
            await callback.answer("❌ Ошибка при отображении статуса", show_alert=True)


# --- Add Note Handler (shows prompt) ---

@router.callback_query(F.data.startswith(CALLBACK_ADD_NOTE))
async def add_note_prompt(callback: CallbackQuery):
    """Prompt user to add a note."""
    hire_id = callback.data[len(CALLBACK_ADD_NOTE):]
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await callback.answer("❌ Карточка не найдена!", show_alert=True)
            return
        
        if not is_user_authorized_for_action(callback, hire, "add_note"):
            await callback.answer(
                "⛔ Недостаточно прав. Только создатель или админ может добавлять заметки.",
                show_alert=True,
            )
            return
    
    # For now, show alert asking to send note via command
    # In a full implementation, this would open a new FSM state
    await callback.answer(
        f"📝 Чтобы добавить заметку, отправьте команду:\n/note {hire_id} <текст заметки>",
        show_alert=True,
    )


# --- No-op handler for disabled buttons ---

@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    """Handle no-op callbacks for disabled buttons."""
    await callback.answer("Это действие уже выполнено.", show_alert=False)
