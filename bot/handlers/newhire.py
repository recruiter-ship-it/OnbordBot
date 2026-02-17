"""
Handler for /newhire command and wizard.
"""
from datetime import datetime
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database import get_session, Hire, HireStatus
from bot.database.models import LeaderStatus, LegalStatus, DevOpsStatus
from bot.services.hire_service import HireService, SettingsService
from bot.states.newhire import NewHireStates
from bot.keyboards.inline import (
    get_checklist_keyboard,
    get_cancel_keyboard,
    get_confirm_keyboard,
    get_hire_card_keyboard,
    CALLBACK_CHECKLIST,
    CALLBACK_CANCEL,
    CALLBACK_CONFIRM,
)
from bot.utils.date_utils import parse_date, format_date, get_now, parse_username, validate_email
from bot.logger import get_logger

logger = get_logger(__name__)

router = Router()


# --- Helper Functions ---

async def get_user_id_by_username(bot: Bot, username: str, chat_id: int) -> Optional[int]:
    """Try to get user ID by username from chat administrators."""
    try:
        admins = await bot.get_chat_administrators(chat_id)
        username_lower = username.lower().lstrip("@")
        for admin in admins:
            if admin.user.username and admin.user.username.lower() == username_lower:
                return admin.user.id
    except Exception as e:
        logger.warning("Failed to get user ID", username=username, error=str(e))
    return None


def format_hire_preview(data: dict) -> str:
    """Format hire data preview for confirmation."""
    checklist_text = "\n".join([f"  • {k}" for k, v in data.get("access_checklist", {}).items() if v])
    
    return f"""
📋 <b>Проверьте данные нового сотрудника:</b>

👤 <b>ФИО:</b> {data.get('full_name', 'Не указано')}
📅 <b>Дата выхода:</b> {format_date(data.get('start_date'))}
💼 <b>Роль:</b> {data.get('role', 'Не указано')}
👤 <b>Лидер:</b> @{data.get('leader_username', 'Не указано')}
⚖️ <b>Юрист:</b> @{data.get('legal_username', 'Не указано')}
🔧 <b>DevOps:</b> @{data.get('devops_username', 'Не указано')}
📧 <b>Почта для документов:</b> {data.get('docs_email', 'Не указано')}
📋 <b>Чеклист доступов:</b>
{checklist_text if checklist_text else '  Не указано'}
📝 <b>Примечания:</b> {data.get('notes', 'Нет')}
"""


# --- Command Handler ---

@router.message(Command("newhire"))
async def cmd_newhire(
    message: Message,
    state: FSMContext,
    is_allowed_creator: bool = False,
):
    """Start the new hire creation wizard."""
    if not is_allowed_creator:
        await message.answer(
            "⛔ У вас нет прав для создания карточки новичка.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return
    
    # Clear any previous state
    await state.clear()
    
    # Initialize data
    await state.update_data(
        access_checklist={},
        notes=None,
    )
    
    await message.answer(
        "🎯 <b>Создание карточки нового сотрудника</b>\n\n"
        "Я задам несколько вопросов для создания карточки.\n"
        "Вы можете отменить процесс в любой момент кнопкой ниже.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML",
    )
    
    await message.answer(
        "👤 Введите ФИО нового сотрудника:",
        reply_markup=get_cancel_keyboard(),
    )
    
    await state.set_state(NewHireStates.full_name)
    logger.info("New hire wizard started", user_id=message.from_user.id)


# --- Cancel Handler ---

@router.callback_query(F.data == CALLBACK_CANCEL)
async def cancel_wizard(callback: CallbackQuery, state: FSMContext):
    """Cancel the wizard."""
    await state.clear()
    await callback.message.edit_text("❌ Создание карточки отменено.")
    await callback.answer()
    logger.info("Wizard cancelled", user_id=callback.from_user.id)


# --- Full Name Handler ---

@router.message(NewHireStates.full_name)
async def process_full_name(message: Message, state: FSMContext):
    """Process full name input."""
    full_name = message.text.strip()
    
    if len(full_name) < 2:
        await message.answer("❌ ФИО слишком короткое. Введите корректное ФИО:")
        return
    
    if len(full_name) > 255:
        await message.answer("❌ ФИО слишком длинное. Максимум 255 символов:")
        return
    
    await state.update_data(full_name=full_name)
    await message.answer(
        "📅 Введите дату выхода сотрудника (формат: YYYY-MM-DD):",
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(NewHireStates.start_date)


# --- Start Date Handler ---

@router.message(NewHireStates.start_date)
async def process_start_date(message: Message, state: FSMContext):
    """Process start date input."""
    date = parse_date(message.text.strip())
    
    if not date:
        await message.answer(
            "❌ Неверный формат даты. Используйте формат YYYY-MM-DD\n"
            "Пример: 2024-02-15"
        )
        return
    
    if date.date() < get_now().date():
        await message.answer(
            "⚠️ Дата выхода в прошлом. Вы уверены?\n"
            "Введите дату снова или нажмите 'Отмена':",
            reply_markup=get_cancel_keyboard(),
        )
        return
    
    await state.update_data(start_date=date)
    await message.answer(
        "💼 Введите роль/позицию нового сотрудника:",
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(NewHireStates.role)


# --- Role Handler ---

@router.message(NewHireStates.role)
async def process_role(message: Message, state: FSMContext):
    """Process role input."""
    role = message.text.strip()
    
    if len(role) < 2:
        await message.answer("❌ Название роли слишком короткое. Введите корректную роль:")
        return
    
    if len(role) > 255:
        await message.answer("❌ Название роли слишком длинное. Максимум 255 символов:")
        return
    
    await state.update_data(role=role)
    await message.answer(
        "👤 Введите Telegram username лидера (с @ или без):",
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(NewHireStates.leader)


# --- Leader Handler ---

@router.message(NewHireStates.leader)
async def process_leader(message: Message, state: FSMContext):
    """Process leader username input."""
    username = parse_username(message.text)
    
    if not username:
        await message.answer(
            "❌ Неверный формат username. Введите корректный Telegram username:\n"
            "Пример: @username или username"
        )
        return
    
    await state.update_data(leader_username=username)
    
    # Show default legal if available
    async with get_session() as session:
        settings_service = SettingsService(session)
        default_legal = await settings_service.get_default_legal() or settings.DEFAULT_LEGAL_USERNAME
    
    default_text = f"\n\n💡 По умолчанию: @{default_legal}" if default_legal else ""
    
    await message.answer(
        f"⚖️ Введите Telegram username юриста (с @ или без):{default_text}",
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(NewHireStates.legal)


# --- Legal Handler ---

@router.message(NewHireStates.legal)
async def process_legal(message: Message, state: FSMContext):
    """Process legal username input."""
    text = message.text.strip()
    
    # Check if user wants to use default
    async with get_session() as session:
        settings_service = SettingsService(session)
        default_legal = await settings_service.get_default_legal() or settings.DEFAULT_LEGAL_USERNAME
    
    if text.lower() in ["по умолчанию", "default", "-", "skip", "пропустить"]:
        if default_legal:
            username = default_legal
        else:
            await message.answer("❌ Username юриста по умолчанию не настроен. Введите username:")
            return
    else:
        username = parse_username(text)
        if not username:
            await message.answer(
                "❌ Неверный формат username. Введите корректный Telegram username:\n"
                "Пример: @username или username"
            )
            return
    
    await state.update_data(legal_username=username)
    
    # Show default devops if available
    default_devops = settings.DEFAULT_DEVOPS_USERNAME
    async with get_session() as session:
        settings_service = SettingsService(session)
        default_devops = await settings_service.get_default_devops() or default_devops
    
    default_text = f"\n\n💡 По умолчанию: @{default_devops}" if default_devops else ""
    
    await message.answer(
        f"🔧 Введите Telegram username DevOps (с @ или без):{default_text}",
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(NewHireStates.devops)


# --- DevOps Handler ---

@router.message(NewHireStates.devops)
async def process_devops(message: Message, state: FSMContext):
    """Process devops username input."""
    text = message.text.strip()
    
    # Check if user wants to use default
    async with get_session() as session:
        settings_service = SettingsService(session)
        default_devops = await settings_service.get_default_devops() or settings.DEFAULT_DEVOPS_USERNAME
    
    if text.lower() in ["по умолчанию", "default", "-", "skip", "пропустить"]:
        if default_devops:
            username = default_devops
        else:
            await message.answer("❌ Username DevOps по умолчанию не настроен. Введите username:")
            return
    else:
        username = parse_username(text)
        if not username:
            await message.answer(
                "❌ Неверный формат username. Введите корректный Telegram username:\n"
                "Пример: @username или username"
            )
            return
    
    await state.update_data(devops_username=username)
    
    await message.answer(
        "📧 Введите email для документов:",
        reply_markup=get_cancel_keyboard(),
    )
    await state.set_state(NewHireStates.docs_email)


# --- Docs Email Handler ---

@router.message(NewHireStates.docs_email)
async def process_docs_email(message: Message, state: FSMContext):
    """Process docs email input."""
    email = message.text.strip()
    
    if not validate_email(email):
        await message.answer(
            "❌ Неверный формат email. Введите корректный email:\n"
            "Пример: user@company.com"
        )
        return
    
    await state.update_data(docs_email=email)
    
    await message.answer(
        "📋 Выберите необходимые доступы из чеклиста:",
        reply_markup=get_checklist_keyboard(),
    )
    await state.set_state(NewHireStates.access_checklist)


# --- Access Checklist Handler ---

@router.callback_query(NewHireStates.access_checklist, F.data.startswith(CALLBACK_CHECKLIST))
async def process_checklist(callback: CallbackQuery, state: FSMContext):
    """Process checklist selection."""
    action = callback.data[len(CALLBACK_CHECKLIST):]
    
    data = await state.get_data()
    checklist = data.get("access_checklist", {})
    
    if action == "done":
        if not checklist:
            await callback.answer("❌ Выберите хотя бы один пункт!", show_alert=True)
            return
        
        await callback.message.edit_text(
            "📝 Введите примечания (или отправьте '-' чтобы пропустить):",
            reply_markup=get_cancel_keyboard(),
        )
        await state.set_state(NewHireStates.notes)
        await callback.answer()
        return
    
    # Toggle checklist item
    if action in checklist:
        del checklist[action]
    else:
        checklist[action] = True
    
    await state.update_data(access_checklist=checklist)
    
    # Get selected items list for display
    selected = list(checklist.keys())
    await callback.message.edit_reply_markup(
        reply_markup=get_checklist_keyboard(selected)
    )
    await callback.answer()


# --- Notes Handler ---

@router.message(NewHireStates.notes)
async def process_notes(message: Message, state: FSMContext):
    """Process notes input and show preview."""
    notes = message.text.strip()
    
    if notes and notes != "-":
        await state.update_data(notes=notes)
    
    data = await state.get_data()
    
    await message.answer(
        format_hire_preview(data),
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(),
    )
    await state.set_state(NewHireStates.confirm)


# --- Confirm Handler ---

@router.callback_query(NewHireStates.confirm, F.data.startswith(CALLBACK_CONFIRM))
async def process_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
):
    """Process confirmation and create hire."""
    action = callback.data[len(CALLBACK_CONFIRM):]
    
    if action != "yes":
        await state.clear()
        await callback.message.edit_text("❌ Создание карточки отменено.")
        await callback.answer()
        return
    
    data = await state.get_data()
    user_id = callback.from_user.id
    
    # Get chat ID for the onboarding group
    chat_id = settings.ONBOARDING_CHAT_ID
    
    if not chat_id:
        await callback.message.edit_text(
            "❌ Ошибка: ID чата для онбординга не настроен. "
            "Обратитесь к администратору."
        )
        await callback.answer()
        logger.error("ONBOARDING_CHAT_ID not configured")
        return
    
    try:
        async with get_session() as session:
            hire_service = HireService(session)
            
            # Try to resolve user IDs for leader, legal, devops
            leader_id = await get_user_id_by_username(bot, data["leader_username"], chat_id)
            legal_id = await get_user_id_by_username(bot, data["legal_username"], chat_id)
            devops_id = await get_user_id_by_username(bot, data["devops_username"], chat_id)
            
            # Create hire
            hire = await hire_service.create_hire(
                full_name=data["full_name"],
                start_date=data["start_date"],
                role=data["role"],
                leader_username=data["leader_username"],
                legal_username=data["legal_username"],
                devops_username=data["devops_username"],
                docs_email=data["docs_email"],
                access_checklist=data["access_checklist"],
                chat_id=chat_id,
                creator_id=user_id,
                notes=data.get("notes"),
                leader_id=leader_id,
                legal_id=legal_id,
                devops_id=devops_id,
            )
            
            # Format and send card to the group chat
            card_text = format_hire_card(hire)
            keyboard = get_hire_card_keyboard(
                hire_id=hire.hire_id,
                leader_status=hire.leader_status,
                legal_status=hire.legal_status,
                devops_status=hire.devops_status,
                overall_status=hire.status,
                is_creator=True,
            )
            
            sent_message = await bot.send_message(
                chat_id=chat_id,
                text=card_text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            
            # Update message ID in database
            await hire_service.update_message_id(hire.hire_id, sent_message.message_id)
            
            # Notify user in private
            await callback.message.edit_text(
                f"✅ Карточка #{hire.hire_id} успешно создана!\n\n"
                f"Сообщение отправлено в чат онбординга.",
                parse_mode="HTML",
            )
            
            # Try to send private notifications to assigned users
            await notify_assigned_users(bot, hire, user_id)
            
            logger.info(
                "Hire created successfully",
                hire_id=hire.hire_id,
                creator_id=user_id,
            )
            
    except Exception as e:
        logger.error("Failed to create hire", error=str(e), exc_info=True)
        await callback.message.edit_text(
            f"❌ Ошибка при создании карточки: {str(e)}\n"
            "Обратитесь к администратору."
        )
    
    await state.clear()
    await callback.answer()


def format_hire_card(hire: Hire) -> str:
    """Format hire card for group chat."""
    # Format checklist
    checklist_items = []
    checklist_labels = {
        "email": "📧 Email",
        "github": "💻 GitHub",
        "jira": "📋 Jira",
        "vpn": "🔒 VPN",
        "slack": "💬 Slack/Telegram",
        "cloud": "☁️ Облако",
        "prod": "🚀 Prod/Stage",
        "other": "📝 Другое",
    }
    
    for key, value in hire.access_checklist.items():
        label = checklist_labels.get(key, key)
        checklist_items.append(label)
    
    checklist_text = "\n    ".join(checklist_items) if checklist_items else "Не указан"
    
    # Format status indicators
    leader_status_icon = "✅" if hire.leader_status == LeaderStatus.ACKNOWLEDGED else "⏳"
    legal_status_icon = "✅" if hire.legal_status == LegalStatus.DOCS_SENT else "⏳"
    devops_status_icon = "✅" if hire.devops_status == DevOpsStatus.ACCESS_GRANTED else "⏳"
    
    status_text = {
        HireStatus.CREATED: "🆕 Создана",
        HireStatus.IN_PROGRESS: "🔄 В процессе",
        HireStatus.READY_FOR_DAY1: "✅ Готов к выходу",
        HireStatus.COMPLETED: "🏁 Завершено",
    }.get(hire.status, hire.status.value)
    
    return f"""
🎯 <b>New hire #{hire.hire_id}</b>

━━━━━━━━━━━━━━━━━━━━

👤 <b>ФИО:</b> {hire.full_name}
📅 <b>Дата выхода:</b> {format_date(hire.start_date)}
💼 <b>Роль:</b> {hire.role}

━━━━━━━━━━━━━━━━━━━━

<b>Назначенные:</b>
👤 Лидер: @{hire.leader_username} {leader_status_icon}
⚖️ Юрист: @{hire.legal_username} {legal_status_icon}
🔧 DevOps: @{hire.devops_username} {devops_status_icon}

━━━━━━━━━━━━━━━━━━━━

📧 <b>Почта:</b> {hire.docs_email}

📋 <b>Доступы:</b>
    {checklist_text}

━━━━━━━━━━━━━━━━━━━━

📊 <b>Статус:</b> {status_text}
"""


async def notify_assigned_users(bot: Bot, hire: Hire, creator_id: int):
    """Send private notifications to assigned users."""
    # Try to notify leader
    if hire.leader_id:
        try:
            await bot.send_message(
                chat_id=hire.leader_id,
                text=f"""
👋 Вы назначены лидером для нового сотрудника!

🎯 <b>New hire #{hire.hire_id}</b>
👤 <b>ФИО:</b> {hire.full_name}
📅 <b>Дата выхода:</b> {format_date(hire.start_date)}
💼 <b>Роль:</b> {hire.role}

Пожалуйста, подтвердите готовность в чате онбординга.
""",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(
                "Failed to notify leader",
                hire_id=hire.hire_id,
                leader_id=hire.leader_id,
                error=str(e),
            )
    
    # Try to notify legal
    if hire.legal_id:
        try:
            await bot.send_message(
                chat_id=hire.legal_id,
                text=f"""
👋 Вам нужно подготовить документы для нового сотрудника!

🎯 <b>New hire #{hire.hire_id}</b>
👤 <b>ФИО:</b> {hire.full_name}
📅 <b>Дата выхода:</b> {format_date(hire.start_date)}
📧 <b>Почта:</b> {hire.docs_email}

Пожалуйста, отправьте документы и отметьте статус в чате онбординга.
""",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(
                "Failed to notify legal",
                hire_id=hire.hire_id,
                legal_id=hire.legal_id,
                error=str(e),
            )
    
    # Try to notify devops
    if hire.devops_id:
        try:
            await bot.send_message(
                chat_id=hire.devops_id,
                text=f"""
👋 Вам нужно настроить доступы для нового сотрудника!

🎯 <b>New hire #{hire.hire_id}</b>
👤 <b>ФИО:</b> {hire.full_name}
📅 <b>Дата выхода:</b> {format_date(hire.start_date)}
💼 <b>Роль:</b> {hire.role}

Пожалуйста, настройте доступы и отметьте статус в чате онбординга.
""",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(
                "Failed to notify devops",
                hire_id=hire.hire_id,
                devops_id=hire.devops_id,
                error=str(e),
            )
