"""
Handler for general commands.
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.database import get_session
from bot.services.hire_service import HireService, SettingsService
from bot.utils.formatting import format_hire_card, format_status_details, format_hire_list_item
from bot.middlewares.access import is_admin, is_creator_or_admin
from bot.logger import get_logger

logger = get_logger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command."""
    await message.answer(
        "👋 Добро пожаловать в Onboarding Bot!\n\n"
        "Этот бот помогает автоматизировать процесс онбординга новых сотрудников.\n\n"
        "📌 Доступные команды:\n"
        "/newhire — создать карточку новичка\n"
        "/status <hire_id> — показать статус\n"
        "/list open — список открытых карточек\n"
        "/setdefaults — настроить умолчания (админ)\n"
        "/help — справка\n\n"
        "Для создания карточки используйте команду /newhire в личке с ботом.",
        parse_mode="HTML",
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    help_text = """
📚 <b>Справка по Onboarding Bot</b>

<b>Команды для всех:</b>
/start — начать работу с ботом
/help — эта справка
/status &lt;hire_id&gt; — показать статус карточки

<b>Команды для рекрутеров:</b>
/newhire — создать карточку новичка (wizard)
/list open — список всех открытых карточек

<b>Команды для админов:</b>
/setdefaults legal=@username devops=@username — настроить умолчания

<b>Статусы карточки:</b>
🆕 CREATED — создана
🔄 IN_PROGRESS — в работе
✅ READY_FOR_DAY1 — готов к выходу
🏁 COMPLETED — завершено

<b>Кнопки под карточкой:</b>
✅ Leader acknowledged — лид подтвердил (только лид)
📄 Docs sent — документы отправлены (только юрист)
🔑 Access granted — доступы выданы (только DevOps)
✅ Завершить — отметить завершённым (рекрутер/админ)
🔄 Переоткрыть — открыть заново (рекрутер/админ)
📝 Заметка — добавить примечание (рекрутер/админ)

<b>Напоминания:</b>
• За 3 дня до выхода — напоминание юристу
• За 1 день до выхода — напоминание DevOps
• После просрочки &gt; 24ч — эскалация рекрутеру

<b>Таймзона:</b> Europe/London
"""
    await message.answer(help_text, parse_mode="HTML")


@router.message(Command("status"))
async def cmd_status(message: Message, command: CommandObject):
    """Handle /status command."""
    args = command.args
    
    if not args:
        await message.answer(
            "❌ Укажите ID карточки: /status &lt;hire_id&gt;\n"
            "Пример: /status ABC1",
            parse_mode="HTML",
        )
        return
    
    hire_id = args.strip().upper()
    
    async with get_session() as session:
        hire_service = HireService(session)
        hire = await hire_service.get_hire(hire_id)
        
        if not hire:
            await message.answer(f"❌ Карточка #{hire_id} не найдена.")
            return
        
        # Show detailed status
        status_text = format_status_details(hire)
        
        # Also show history
        history = await hire_service.get_history(hire_id)
        
        if history:
            status_text += "\n\n<b>📜 История:</b>"
            for entry in history[-10:]:  # Last 10 entries
                actor = f"@{entry.actor_username}" if entry.actor_username else f"ID:{entry.actor_id}"
                time = entry.ts.strftime("%d.%m %H:%M")
                status_text += f"\n• {time} — {actor}: {entry.action}"
        
        await message.answer(status_text, parse_mode="HTML")


@router.message(Command("list"))
async def cmd_list(message: Message, command: CommandObject):
    """Handle /list command."""
    args = command.args.strip().lower() if command.args else ""
    
    if args != "open":
        await message.answer(
            "📌 Используйте: /list open — для списка открытых карточек"
        )
        return
    
    async with get_session() as session:
        hire_service = HireService(session)
        hires = await hire_service.get_open_hires()
        
        if not hires:
            await message.answer("✅ Нет открытых карточек.")
            return
        
        text = f"📋 <b>Открытые карточки ({len(hires)}):</b>\n\n"
        
        for hire in hires:
            text += format_hire_list_item(hire) + "\n\n"
        
        # Split if too long
        if len(text) > 4000:
            parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
            for part in parts:
                await message.answer(part, parse_mode="HTML")
        else:
            await message.answer(text, parse_mode="HTML")


@router.message(Command("setdefaults"))
async def cmd_setdefaults(message: Message, command: CommandObject):
    """Handle /setdefaults command (admin only)."""
    user_id = message.from_user.id
    
    if not is_admin(user_id):
        await message.answer("❌ Эта команда доступна только администраторам.")
        return
    
    args = command.args
    
    if not args:
        # Show current defaults
        async with get_session() as session:
            settings_service = SettingsService(session)
            legal = await settings_service.get_default_legal() or "не установлен"
            devops = await settings_service.get_default_devops() or "не установлен"
        
        await message.answer(
            f"📌 Текущие умолчания:\n"
            f"• Legal: @{legal}\n"
            f"• DevOps: @{devops}\n\n"
            f"Для изменения: /setdefaults legal=@username devops=@username",
            parse_mode="HTML",
        )
        return
    
    # Parse arguments
    legal_username = None
    devops_username = None
    
    import re
    for part in args.split():
        if part.startswith("legal="):
            value = part[6:].lstrip("@")
            if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', value):
                legal_username = value
        elif part.startswith("devops="):
            value = part[7:].lstrip("@")
            if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', value):
                devops_username = value
    
    if not legal_username and not devops_username:
        await message.answer(
            "❌ Неверный формат. Пример:\n"
            "/setdefaults legal=@legal_team devops=@devops_team"
        )
        return
    
    async with get_session() as session:
        settings_service = SettingsService(session)
        
        if legal_username:
            await settings_service.set_default_legal(legal_username)
        
        if devops_username:
            await settings_service.set_default_devops(devops_username)
        
        legal = await settings_service.get_default_legal()
        devops = await settings_service.get_default_devops()
    
    await message.answer(
        f"✅ Умолчания обновлены:\n"
        f"• Legal: @{legal}\n"
        f"• DevOps: @{devops}",
        parse_mode="HTML",
    )
    
    logger.info(
        "Defaults updated",
        user_id=user_id,
        legal=legal_username,
        devops=devops_username,
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message):
    """Handle /cancel command (used in wizard)."""
    # This is handled by the FSM, but provide a message for direct use
    await message.answer(
        "ℹ️ Команда /cancel используется для отмены создания карточки.\n"
        "Если вы сейчас не создаёте карточку, эта команда ничего не делает."
    )
