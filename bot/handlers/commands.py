"""
Handler for general commands (/status, /list, /help, etc.).
"""
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database import get_session
from bot.database.models import HireStatus, LeaderStatus, LegalStatus, DevOpsStatus
from bot.services.hire_service import HireService, SettingsService
from bot.utils.date_utils import format_date, format_datetime, days_until
from bot.utils.date_utils import parse_username
from bot.logger import get_logger

logger = get_logger(__name__)

router = Router()


# --- Help Command ---

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Show help message."""
    is_admin = message.from_user.id in settings.admin_ids_list
    is_creator = message.from_user.id in settings.allowed_creators_list
    
    help_text = """
📚 <b>Справка по боту онбординга</b>

Бот автоматизирует процесс онбординга новых сотрудников.

<b>Доступные команды:</b>

/newhire — Создать карточку нового сотрудника (только для HR)
/status &lt;hire_id&gt; — Показать статус карточки
/list open — Список всех открытых карточек
/cancel — Отменить текущее действие (в визарде)
/help — Эта справка
"""
    
    if is_admin:
        help_text += """
<b>Команды администратора:</b>

/setdefaults legal=@username devops=@username — Установить username юриста и DevOps по умолчанию
"""
    
    help_text += """
<b>Статусы карточки:</b>

🆕 CREATED — Карточка создана
🔄 IN_PROGRESS — В процессе работы
✅ READY_FOR_DAY1 — Готов к первому дню
🏁 COMPLETED — Завершено

<b>Статусы ответственных:</b>

👤 Leader: PENDING → ACKNOWLEDGED
⚖️ Legal: PENDING → DOCS_SENT
🔧 DevOps: PENDING → ACCESS_GRANTED

<b>Напоминания:</b>

• За 3 дня до выхода: напоминание юристу
• За 1 день до выхода: напоминание DevOps
• При просрочке: эскалация рекрутеру

❓ Вопросы? Обратитесь к администратору бота.
"""
    
    await message.answer(help_text, parse_mode="HTML")


# --- Status Command ---

@router.message(Command("status"))
async def cmd_status(message: Message, command: CommandObject):
    """Show status of a hire."""
    hire_id = command.args
    
    if not hire_id:
        await message.answer(
            "❌ Укажите ID карточки.\n"
            "Пример: /status ABC123"
        )
        return
    
    hire_id = hire_id.strip().upper()
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await message.answer(f"❌ Карточка #{hire_id} не найдена.")
            return
        
        # Get history
        history = await hire_service.get_history(hire_id)
        
        # Calculate days until start
        days = days_until(hire.start_date)
        if days > 0:
            days_text = f"⏳ До выхода: {days} дн."
        elif days == 0:
            days_text = "📅 Сегодня день выхода!"
        else:
            days_text = f"⚠️ Просрочено на {abs(days)} дн."
        
        # Format status icons
        leader_icon = "✅" if hire.leader_status == LeaderStatus.ACKNOWLEDGED else "⏳"
        legal_icon = "✅" if hire.legal_status == LegalStatus.DOCS_SENT else "⏳"
        devops_icon = "✅" if hire.devops_status == DevOpsStatus.ACCESS_GRANTED else "⏳"
        
        status_text = f"""
📊 <b>Статус карточки #{hire.hire_id}</b>

━━━━━━━━━━━━━━━━━━━━

👤 <b>ФИО:</b> {hire.full_name}
📅 <b>Дата выхода:</b> {format_date(hire.start_date)}
💼 <b>Роль:</b> {hire.role}
{days_text}

━━━━━━━━━━━━━━━━━━━━

<b>Статусы ответственных:</b>

👤 Лидер (@{hire.leader_username}): {leader_icon} {hire.leader_status.value}
⚖️ Юрист (@{hire.legal_username}): {legal_icon} {hire.legal_status.value}
🔧 DevOps (@{hire.devops_username}): {devops_icon} {hire.devops_status.value}

━━━━━━━━━━━━━━━━━━━━

<b>Общий статус:</b> {hire.status.value}

📧 <b>Почта:</b> {hire.docs_email}
"""
        
        if hire.notes:
            notes_preview = hire.notes[:200] + "..." if len(hire.notes) > 200 else hire.notes
            status_text += f"\n📝 <b>Заметки:</b>\n{notes_preview}\n"
        
        # Add recent history
        status_text += "\n━━━━━━━━━━━━━━━━━━━━\n"
        status_text += "<b>Последние изменения:</b>\n"
        
        for h in history[-5:]:
            actor = f"@{h.actor_username}" if h.actor_username else f"ID:{h.actor_id}"
            status_text += f"• {format_datetime(h.ts)} — {h.action} ({actor})\n"
        
        await message.answer(status_text, parse_mode="HTML")


# --- List Command ---

@router.message(Command("list"))
async def cmd_list(message: Message, command: CommandObject):
    """List all open hires."""
    filter_type = command.args.strip().lower() if command.args else "open"
    
    async with get_session() as session:
        hire_service = HireService(session)
        
        if filter_type == "open":
            hires = await hire_service.get_open_hires()
            title = "📋 <b>Открытые карточки</b>\n"
        elif filter_type == "all":
            hires = await hire_service.get_hires_by_status(exclude_completed=False)
            title = "📋 <b>Все карточки</b>\n"
        elif filter_type == "completed":
            hires = await hire_service.get_hires_by_status(statuses=[HireStatus.COMPLETED])
            title = "🏁 <b>Завершённые карточки</b>\n"
        else:
            await message.answer(
                "❌ Неверный фильтр. Используйте:\n"
                "/list open — открытые\n"
                "/list all — все\n"
                "/list completed — завершённые"
            )
            return
        
        if not hires:
            await message.answer(f"{title}\nНет карточек.")
            return
        
        # Format list
        text = title + "\n━━━━━━━━━━━━━━━━━━━━\n"
        
        for hire in hires[:20]:  # Limit to 20
            days = days_until(hire.start_date)
            
            if days > 0:
                days_text = f"({days} дн.)"
            elif days == 0:
                days_text = "(сегодня!)"
            else:
                days_text = f"(просрочено {abs(days)} дн.)"
            
            # Status indicators
            indicators = []
            if hire.leader_status == LeaderStatus.ACKNOWLEDGED:
                indicators.append("👤✅")
            if hire.legal_status == LegalStatus.DOCS_SENT:
                indicators.append("⚖️✅")
            if hire.devops_status == DevOpsStatus.ACCESS_GRANTED:
                indicators.append("🔧✅")
            
            indicator_text = " ".join(indicators) if indicators else "⏳"
            
            text += f"""
🎯 <b>#{hire.hire_id}</b> {days_text}
👤 {hire.full_name}
💼 {hire.role}
📅 {format_date(hire.start_date)}
{indicator_text}
"""
        
        if len(hires) > 20:
            text += f"\n... и ещё {len(hires) - 20} карточек"
        
        await message.answer(text, parse_mode="HTML")


# --- Set Defaults Command (Admin only) ---

@router.message(Command("setdefaults"))
async def cmd_setdefaults(
    message: Message, 
    command: CommandObject,
    is_admin: bool = False,
):
    """Set default legal and devops usernames (admin only)."""
    if not is_admin:
        await message.answer("⛔ Эта команда доступна только администраторам.")
        return
    
    args = command.args
    
    if not args:
        await message.answer(
            "❌ Укажите параметры.\n"
            "Пример: /setdefaults legal=@lawyer devops=@devops"
        )
        return
    
    # Parse arguments
    legal_username = None
    devops_username = None
    
    parts = args.split()
    for part in parts:
        if part.startswith("legal="):
            legal_username = parse_username(part[6:])
        elif part.startswith("devops="):
            devops_username = parse_username(part[7:])
    
    async with get_session() as session:
        settings_service = SettingsService(session)
        
        if legal_username:
            await settings_service.set_default_legal(legal_username)
        
        if devops_username:
            await settings_service.set_default_devops(devops_username)
    
    # Get current values
    async with get_session() as session:
        settings_service = SettingsService(session)
        current_legal = await settings_service.get_default_legal() or settings.DEFAULT_LEGAL_USERNAME
        current_devops = await settings_service.get_default_devops() or settings.DEFAULT_DEVOPS_USERNAME
    
    await message.answer(
        f"✅ Настройки по умолчанию обновлены:\n\n"
        f"⚖️ Юрист: @{current_legal or 'не задан'}\n"
        f"🔧 DevOps: @{current_devops or 'не задан'}",
        parse_mode="HTML",
    )
    
    logger.info(
        "Defaults updated",
        user_id=message.from_user.id,
        legal=legal_username,
        devops=devops_username,
    )


# --- Note Command ---

@router.message(Command("note"))
async def cmd_note(message: Message, command: CommandObject):
    """Add a note to a hire card."""
    args = command.args
    
    if not args:
        await message.answer(
            "❌ Укажите ID карточки и текст заметки.\n"
            "Пример: /note ABC123 Нужно подготовить ноутбук"
        )
        return
    
    parts = args.split(maxsplit=1)
    
    if len(parts) < 2:
        await message.answer(
            "❌ Укажите текст заметки.\n"
            "Пример: /note ABC123 Нужно подготовить ноутбук"
        )
        return
    
    hire_id = parts[0].strip().upper()
    note_text = parts[1].strip()
    
    if len(note_text) > 1000:
        await message.answer("❌ Заметка слишком длинная (максимум 1000 символов).")
        return
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await message.answer(f"❌ Карточка #{hire_id} не найдена.")
            return
        
        # Check permissions
        user_id = message.from_user.id
        is_creator = user_id == hire.creator_id
        is_admin = user_id in settings.admin_ids_list
        
        if not is_creator and not is_admin:
            await message.answer("⛔ Недостаточно прав для добавления заметки.")
            return
        
        # Add note
        await hire_service.add_note(
            hire_id=hire_id,
            note=note_text,
            actor_id=user_id,
            actor_username=message.from_user.username,
        )
        
        await message.answer(f"✅ Заметка добавлена к карточке #{hire_id}")
        
        logger.info(
            "Note added via command",
            hire_id=hire_id,
            user_id=user_id,
        )


# --- Cancel Command ---

@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """Generic cancel command (handled by FSM if in wizard)."""
    await message.answer(
        "❌ Нет активного действия для отмены.\n"
        "Эта команда используется для отмены создания карточки."
    )
