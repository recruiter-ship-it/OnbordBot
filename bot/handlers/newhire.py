"""
Handler for /newhire command and wizard.
"""
from datetime import datetime
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database import get_session, HireStatus
from bot.database.models import Hire
from bot.services.hire_service import HireService, SettingsService
from bot.states.newhire import NewHireStates
from bot.keyboards.inline import (
    get_cancel_keyboard,
    get_confirm_keyboard,
    get_checklist_keyboard,
    CALLBACK_CHECKLIST,
    CALLBACK_CANCEL,
    CALLBACK_CONFIRM,
)
from bot.utils.formatting import (
    parse_date,
    parse_username,
    parse_email,
    format_hire_card,
)
from bot.middlewares.access import is_allowed_creator, is_creator_or_admin
from bot.logger import get_logger

logger = get_logger(__name__)

router = Router()


# Checklist options
CHECKLIST_ITEMS = {
    "email": "📧 Email",
    "github": "💻 GitHub",
    "jira": "📋 Jira",
    "vpn": "🔒 VPN",
    "slack": "💬 Slack/Telegram",
    "cloud": "☁️ Облако",
    "prod": "🚀 Prod/Stage",
    "other": "📝 Другое",
}


@router.message(Command("newhire"))
async def cmd_newhire(message: Message, state: FSMContext):
    """Start the new hire wizard."""
    user_id = message.from_user.id
    
    # Check if user is allowed
    if not is_allowed_creator(user_id):
        await message.answer("❌ У вас нет прав для создания карточки новичка.")
        return
    
    # Clear any previous state
    await state.clear()
    
    # Initialize wizard data
    async with get_session() as session:
        settings_service = SettingsService(session)
        default_legal = await settings_service.get_default_legal() or settings.DEFAULT_LEGAL_USERNAME
        default_devops = await settings_service.get_default_devops() or settings.DEFAULT_DEVOPS_USERNAME
    
    await state.update_data(
        legal_username=default_legal,
        devops_username=default_devops,
        access_checklist=[],
    )
    
    await message.answer(
        "🎯 <b>Создание карточки новичка</b>\n\n"
        "Введите ФИО нового сотрудника:",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(),
    )
    
    await state.set_state(NewHireStates.full_name)
    logger.info("New hire wizard started", user_id=user_id)


@router.message(NewHireStates.full_name)
async def process_full_name(message: Message, state: FSMContext):
    """Process full name input."""
    full_name = message.text.strip()
    
    if len(full_name) < 2:
        await message.answer("❌ ФИО должно содержать минимум 2 символа. Попробуйте снова:")
        return
    
    await state.update_data(full_name=full_name)
    
    await message.answer(
        "📅 Введите дату выхода в формате <b>YYYY-MM-DD</b>:\n"
        "(например, 2024-02-15)",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard(),
    )
    
    await state.set_state(NewHireStates.start_date)


@router.message(NewHireStates.start_date)
async def process_start_date(message: Message, state: FSMContext):
    """Process start date input."""
    date = parse_date(message.text.strip())
    
    if not date:
        await message.answer(
            "❌ Неверный формат даты. Используйте формат <b>YYYY-MM-DD</b>:\n"
            "(например, 2024-02-15)",
            parse_mode="HTML",
        )
        return
    
    await state.update_data(start_date=date)
    
    await message.answer(
        "💼 Введите роль/позицию нового сотрудника:",
        reply_markup=get_cancel_keyboard(),
    )
    
    await state.set_state(NewHireStates.role)


@router.message(NewHireStates.role)
async def process_role(message: Message, state: FSMContext):
    """Process role input."""
    role = message.text.strip()
    
    if len(role) < 2:
        await message.answer("❌ Роль должна содержать минимум 2 символа. Попробуйте снова:")
        return
    
    await state.update_data(role=role)
    
    await message.answer(
        "👔 Введите Telegram @username лидера команды:\n"
        "(например, @username или просто username)",
        reply_markup=get_cancel_keyboard(),
    )
    
    await state.set_state(NewHireStates.leader)


@router.message(NewHireStates.leader)
async def process_leader(message: Message, state: FSMContext):
    """Process leader username input."""
    username = parse_username(message.text)
    
    if not username:
        await message.answer(
            "❌ Неверный формат username. Введите @username или просто username:"
        )
        return
    
    await state.update_data(leader_username=username)
    
    data = await state.get_data()
    default_legal = data.get("legal_username", "")
    
    await message.answer(
        f"⚖️ Введите Telegram @username юриста:\n"
        f"(по умолчанию: @{default_legal})",
        reply_markup=get_cancel_keyboard(),
    )
    
    await state.set_state(NewHireStates.legal)


@router.message(NewHireStates.legal)
async def process_legal(message: Message, state: FSMContext):
    """Process legal username input."""
    text = message.text.strip()
    
    if text:
        username = parse_username(text)
        if not username:
            await message.answer(
                "❌ Неверный формат username. Введите @username или оставьте пустым для значения по умолчанию:"
            )
            return
    else:
        data = await state.get_data()
        username = data.get("legal_username", "")
    
    await state.update_data(legal_username=username)
    
    data = await state.get_data()
    default_devops = data.get("devops_username", "")
    
    await message.answer(
        f"🔧 Введите Telegram @username DevOps:\n"
        f"(по умолчанию: @{default_devops})",
        reply_markup=get_cancel_keyboard(),
    )
    
    await state.set_state(NewHireStates.devops)


@router.message(NewHireStates.devops)
async def process_devops(message: Message, state: FSMContext):
    """Process devops username input."""
    text = message.text.strip()
    
    if text:
        username = parse_username(text)
        if not username:
            await message.answer(
                "❌ Неверный формат username. Введите @username или оставьте пустым для значения по умолчанию:"
            )
            return
    else:
        data = await state.get_data()
        username = data.get("devops_username", "")
    
    await state.update_data(devops_username=username)
    
    await message.answer(
        "📧 Введите email для документов:",
        reply_markup=get_cancel_keyboard(),
    )
    
    await state.set_state(NewHireStates.docs_email)


@router.message(NewHireStates.docs_email)
async def process_docs_email(message: Message, state: FSMContext):
    """Process docs email input."""
    email = parse_email(message.text)
    
    if not email:
        await message.answer("❌ Неверный формат email. Попробуйте снова:")
        return
    
    await state.update_data(docs_email=email)
    
    # Show checklist selection
    await message.answer(
        "📋 Выберите необходимые доступы:",
        reply_markup=get_checklist_keyboard([]),
    )
    
    await state.set_state(NewHireStates.access_checklist)


@router.callback_query(NewHireStates.access_checklist, F.data.startswith(CALLBACK_CHECKLIST))
async def process_checklist(callback: CallbackQuery, state: FSMContext):
    """Process checklist selection."""
    data = await state.get_data()
    selected = data.get("access_checklist", [])
    
    action = callback.data[len(CALLBACK_CHECKLIST):]
    
    if action == "done":
        if not selected:
            await callback.answer("❌ Выберите хотя бы один пункт!", show_alert=True)
            return
        
        await state.update_data(access_checklist=selected)
        
        await callback.message.edit_text(
            "📝 Введите примечания (опционально) или отправьте '-' чтобы пропустить:",
            reply_markup=get_cancel_keyboard(),
        )
        
        await state.set_state(NewHireStates.notes)
        await callback.answer()
        return
    
    # Toggle selection
    if action in selected:
        selected = [x for x in selected if x != action]
    else:
        selected = selected + [action]
    
    await state.update_data(access_checklist=selected)
    
    await callback.message.edit_reply_markup(
        reply_markup=get_checklist_keyboard(selected)
    )
    await callback.answer()


@router.message(NewHireStates.notes)
async def process_notes(message: Message, state: FSMContext):
    """Process notes input and show confirmation."""
    notes = message.text.strip()
    
    if notes == "-":
        notes = None
    
    await state.update_data(notes=notes)
    
    # Show confirmation
    data = await state.get_data()
    
    # Format preview
    checklist_str = ", ".join([
        CHECKLIST_ITEMS.get(x, x) for x in data.get("access_checklist", [])
    ])
    
    preview = f"""
🎯 <b>Проверьте данные:</b>

<b>👤 ФИО:</b> {data.get('full_name')}
<b>📅 Дата выхода:</b> {data.get('start_date').strftime('%Y-%m-%d')}
<b>💼 Роль:</b> {data.get('role')}
<b>👔 Leader:</b> @{data.get('leader_username')}
<b>⚖️ Legal:</b> @{data.get('legal_username')}
<b>🔧 DevOps:</b> @{data.get('devops_username')}
<b>📧 Email:</b> {data.get('docs_email')}
<b>📋 Доступы:</b> {checklist_str}
"""
    if notes:
        preview += f"<b>📝 Примечания:</b> {notes}"
    
    await message.answer(
        preview,
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(),
    )
    
    await state.set_state(NewHireStates.confirm)


@router.callback_query(NewHireStates.confirm, F.data.startswith(CALLBACK_CONFIRM))
async def confirm_creation(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Confirm and create the hire."""
    data = await state.get_data()
    
    # Create checklist dict
    checklist_dict = {item: True for item in data.get("access_checklist", [])}
    
    try:
        async with get_session() as session:
            hire_service = HireService(session)
            
            # Create hire
            hire = await hire_service.create_hire(
                full_name=data["full_name"],
                start_date=data["start_date"],
                role=data["role"],
                leader_username=data["leader_username"],
                legal_username=data["legal_username"],
                devops_username=data["devops_username"],
                docs_email=data["docs_email"],
                access_checklist=checklist_dict,
                notes=data.get("notes"),
                chat_id=settings.ONBOARDING_CHAT_ID,
                creator_id=callback.from_user.id,
            )
            
            # Format card
            card = format_hire_card(hire)
            
            # Send to onboarding chat
            from bot.keyboards.inline import get_hire_card_keyboard
            
            chat_message = await bot.send_message(
                chat_id=settings.ONBOARDING_CHAT_ID,
                text=card,
                parse_mode="HTML",
                reply_markup=get_hire_card_keyboard(
                    hire_id=hire.hire_id,
                    leader_status=hire.leader_status,
                    legal_status=hire.legal_status,
                    devops_status=hire.devops_status,
                    overall_status=hire.status,
                    is_creator=True,
                ),
            )
            
            # Update message ID
            await hire_service.update_message_id(hire.hire_id, chat_message.message_id)
            
            # Send confirmation to user
            await callback.message.edit_text(
                f"✅ Карточка #{hire.hire_id} успешно создана!\n\n"
                f"Сообщение отправлено в чат онбординга.",
                parse_mode="HTML",
            )
            
            # Notify responsible people
            await _notify_responsible(bot, hire)
            
            logger.info(
                "Hire created successfully",
                hire_id=hire.hire_id,
                creator_id=callback.from_user.id,
            )
    
    except Exception as e:
        logger.error("Failed to create hire", error=str(e))
        await callback.message.edit_text(
            f"❌ Ошибка при создании карточки: {str(e)}",
            parse_mode="HTML",
        )
    
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == CALLBACK_CANCEL)
async def cancel_wizard(callback: CallbackQuery, state: FSMContext):
    """Cancel the wizard."""
    await state.clear()
    await callback.message.edit_text("❌ Создание карточки отменено.")
    await callback.answer()


async def _notify_responsible(bot: Bot, hire: Hire) -> None:
    """Notify responsible people about new hire."""
    mentions = []
    
    # Try to mention in the chat
    try:
        await bot.send_message(
            chat_id=settings.ONBOARDING_CHAT_ID,
            text=(
                f"🔔 Уведомление для ответственных по #{hire.hire_id}:\n\n"
                f"@{hire.leader_username} — подтвердите получение\n"
                f"@{hire.legal_username} — подготовьте документы\n"
                f"@{hire.devops_username} — настройте доступы"
            ),
            parse_mode="HTML",
        )
    except Exception as e:
        logger.warning("Failed to send notification", error=str(e))
