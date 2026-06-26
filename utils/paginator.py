from __future__ import annotations

import math
from typing import Any

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import USERS_PER_PAGE


def build_session_keyboard(
    sessions: list[dict],
    page: int = 0,
) -> InlineKeyboardMarkup:
    """
    Build a paginated inline keyboard of session buttons.
    Each button callback: `otp:{session_id}`
    Navigation callbacks: `page:{page_num}`
    """
    total = len(sessions)
    total_pages = max(1, math.ceil(total / USERS_PER_PAGE))
    page = max(0, min(page, total_pages - 1))

    start = page * USERS_PER_PAGE
    end = start + USERS_PER_PAGE
    page_sessions = sessions[start:end]

    buttons: list[list[InlineKeyboardButton]] = []

    for s in page_sessions:
        sid = str(s["_id"])
        name = s.get("user_name") or "Unknown"
        phone = s.get("phone_number", "")
        status_icon = "✅" if s.get("status") == "active" else "❌"
        label = f"{status_icon} {name} ({phone})"
        buttons.append([InlineKeyboardButton(label, callback_data=f"otp:{sid}")])

    # Navigation row
    nav: list[InlineKeyboardButton] = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀ Prev", callback_data=f"page:{page - 1}"))
    nav.append(
        InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="noop")
    )
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶", callback_data=f"page:{page + 1}"))

    if nav:
        buttons.append(nav)

    # Utility row
    buttons.append([
        InlineKeyboardButton("🔍 Search Phone", callback_data="search:phone"),
        InlineKeyboardButton("🔍 Search Name", callback_data="search:name"),
    ])
    buttons.append([
        InlineKeyboardButton("📊 Stats", callback_data="stats"),
        InlineKeyboardButton("🏥 Health Check", callback_data="healthcheck"),
    ])

    return InlineKeyboardMarkup(buttons)


def build_otp_keyboard(session_id: str) -> InlineKeyboardMarkup:
    """Action buttons shown after an OTP is fetched."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Refresh OTP", callback_data=f"refresh:{session_id}"),
            InlineKeyboardButton("◀ Back", callback_data="back:list"),
        ]
    ])
