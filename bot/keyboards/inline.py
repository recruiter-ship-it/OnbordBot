"""
Inline keyboards for the Onboarding Bot.
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.database.models import (
    HireStatus,
    LeaderStatus,
    LegalStatus,
    DevOpsStatus,
)


# Callback data prefixes
CALLBACK_LEADER_ACK = "leader_ack:"
CALLBACK_DOCS_SENT = "docs_sent:"
CALLBACK_ACCESS_GRANTED = "access_granted:"
CALLBACK_COMPLETE = "complete:"
CALLBACK_REOPEN = "reopen:"
CALLBACK_SHOW_STATUS = "show_status:"
CALLBACK_ADD_NOTE = "add_note:"
CALLBACK_CANCEL = "cancel"
CALLBACK_CONFIRM = "confirm:"
CALLBACK_CHECKLIST = "checklist:"


def get_checklist_keyboard(selected: list = None) -> InlineKeyboardMarkup:
    """Get keyboard for selecting access checklist items."""
    if selected is None:
        selected = []
    
    items = [
        ("📧 Email", "email"),
        ("💻 GitHub", "github"),
        ("📋 Jira", "jira"),
        ("🔒 VPN", "vpn"),
        ("💬 Slack/Telegram", "slack"),
        ("☁️ Облако", "cloud"),
        ("🚀 Prod/Stage", "prod"),
        ("📝 Другое", "other"),
    ]
    
    builder = InlineKeyboardBuilder()
    
    for label, value in items:
        prefix = "✅ " if value in selected else ""
        builder.button(
            text=f"{prefix}{label}",
            callback_data=f"{CALLBACK_CHECKLIST}{value}"
        )
    
    builder.adjust(2)
    
    # Add done button
    builder.row(
        InlineKeyboardButton(
            text="✅ Готово",
            callback_data=f"{CALLBACK_CHECKLIST}done"
        )
    )
    
    return builder.as_markup()


def get_hire_card_keyboard(
    hire_id: str,
    leader_status: LeaderStatus,
    legal_status: LegalStatus,
    devops_status: DevOpsStatus,
    overall_status: HireStatus,
    is_creator: bool = False,
    is_admin: bool = False,
) -> InlineKeyboardMarkup:
    """Get inline keyboard for hire card."""
    builder = InlineKeyboardBuilder()
    
    # Status buttons with visual indicators
    if leader_status == LeaderStatus.PENDING:
        builder.button(
            text="👤 Лидер подтвердил",
            callback_data=f"{CALLBACK_LEADER_ACK}{hire_id}"
        )
    else:
        builder.button(
            text=f"👤 Лидер: ✅ Подтверждено",
            callback_data="noop"
        )
    
    if legal_status == LegalStatus.PENDING:
        builder.button(
            text="📄 Документы отправлены",
            callback_data=f"{CALLBACK_DOCS_SENT}{hire_id}"
        )
    else:
        builder.button(
            text=f"📄 Документы: ✅ Отправлены",
            callback_data="noop"
        )
    
    if devops_status == DevOpsStatus.PENDING:
        builder.button(
            text="🔐 Доступы выданы",
            callback_data=f"{CALLBACK_ACCESS_GRANTED}{hire_id}"
        )
    else:
        builder.button(
            text=f"🔐 Доступы: ✅ Выданы",
            callback_data="noop"
        )
    
    builder.adjust(1)
    
    # Info button
    builder.row(
        InlineKeyboardButton(
            text="📊 Подробнее",
            callback_data=f"{CALLBACK_SHOW_STATUS}{hire_id}"
        )
    )
    
    # Admin/Creator only buttons
    if is_creator or is_admin:
        if overall_status == HireStatus.COMPLETED:
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Открыть снова",
                    callback_data=f"{CALLBACK_REOPEN}{hire_id}"
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="🏁 Завершить",
                    callback_data=f"{CALLBACK_COMPLETE}{hire_id}"
                ),
                InlineKeyboardButton(
                    text="📝 Заметка",
                    callback_data=f"{CALLBACK_ADD_NOTE}{hire_id}"
                )
            )
    
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Get cancel button for wizard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data=CALLBACK_CANCEL)]
        ]
    )


def get_confirm_keyboard() -> InlineKeyboardMarkup:
    """Get confirmation keyboard."""
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Создать карточку", callback_data=f"{CALLBACK_CONFIRM}yes")
    builder.button(text="❌ Отмена", callback_data=CALLBACK_CANCEL)
    builder.adjust(2)
    return builder.as_markup()


def get_status_keyboard(hire_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for status view."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Назад к карточке", 
                callback_data=f"back_to_card:{hire_id}"
            )]
        ]
    )
