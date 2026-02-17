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
    
    # Leader button
    if leader_status == LeaderStatus.PENDING:
        builder.button(
            text="✅ Leader acknowledged",
            callback_data=f"{CALLBACK_LEADER_ACK}{hire_id}"
        )
    else:
        builder.button(
            text=f"✅ Leader: {leader_status.value}",
            callback_data="noop"
        )
    
    # Legal button
    if legal_status == LegalStatus.PENDING:
        builder.button(
            text="📄 Docs sent",
            callback_data=f"{CALLBACK_DOCS_SENT}{hire_id}"
        )
    else:
        builder.button(
            text=f"📄 Docs: {legal_status.value}",
            callback_data="noop"
        )
    
    # DevOps button
    if devops_status == DevOpsStatus.PENDING:
        builder.button(
            text="🔑 Access granted",
            callback_data=f"{CALLBACK_ACCESS_GRANTED}{hire_id}"
        )
    else:
        builder.button(
            text=f"🔑 Access: {devops_status.value}",
            callback_data="noop"
        )
    
    builder.adjust(1)
    
    # Status and actions row
    builder.row(
        InlineKeyboardButton(
            text="ℹ️ Статус",
            callback_data=f"{CALLBACK_SHOW_STATUS}{hire_id}"
        )
    )
    
    # Admin/Creator only buttons
    if is_creator or is_admin:
        if overall_status == HireStatus.COMPLETED:
            builder.row(
                InlineKeyboardButton(
                    text="🔄 Переоткрыть",
                    callback_data=f"{CALLBACK_REOPEN}{hire_id}"
                )
            )
        else:
            builder.row(
                InlineKeyboardButton(
                    text="✅ Завершить",
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
    builder.button(text="✅ Подтвердить", callback_data=f"{CALLBACK_CONFIRM}yes")
    builder.button(text="❌ Отмена", callback_data=CALLBACK_CANCEL)
    builder.adjust(2)
    return builder.as_markup()


def get_status_keyboard(hire_id: str) -> InlineKeyboardMarkup:
    """Get keyboard for status view."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="◀️ Назад", 
                callback_data=f"back_to_card:{hire_id}"
            )]
        ]
    )
