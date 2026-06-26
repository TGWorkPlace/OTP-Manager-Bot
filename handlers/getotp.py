from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from config import ADMIN_ID
from database import db
from utils.paginator import build_session_keyboard

logger = logging.getLogger("otp_bot.getotp")


def admin_only(_, __, message: Message) -> bool:  # type: ignore[override]
    return message.from_user is not None and message.from_user.id == ADMIN_ID


admin_filter = filters.create(admin_only)


@Client.on_message(filters.private & admin_filter & filters.command("getotp"))
async def getotp_handler(client: Client, message: Message) -> None:
    sessions = await db.get_all_sessions()

    if not sessions:
        await message.reply_text(
            "**No saved sessions found.**\n\nAdd sessions via the /login flow.",
            quote=True,
        )
        return

    keyboard = build_session_keyboard(sessions, page=0)
    await message.reply_text(
        f"**📋 Saved Accounts** — {len(sessions)} total\n\nSelect an account to fetch OTP:",
        reply_markup=keyboard,
        quote=True,
    )
    logger.info("Admin opened /getotp — %d sessions", len(sessions))


@Client.on_message(filters.private & admin_filter & filters.command("stats"))
async def stats_handler(client: Client, message: Message) -> None:
    counts = await db.count_sessions()
    last_time = await db.get_last_otp_time()
    last_str = last_time.strftime("%Y-%m-%d %H:%M UTC") if last_time else "Never"

    await message.reply_text(
        "**📊 Session Statistics**\n\n"
        f"Total Sessions: `{counts['total']}`\n"
        f"✅ Active: `{counts['active']}`\n"
        f"❌ Invalid: `{counts['invalid']}`\n"
        f"💀 Dead: `{counts['dead']}`\n"
        f"🕐 Last OTP Check: `{last_str}`",
        quote=True,
    )


@Client.on_message(filters.private & admin_filter & filters.command("search"))
async def search_handler(client: Client, message: Message) -> None:
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text(
            "**Usage:** `/search <phone or username>`", quote=True
        )
        return

    query = parts[1].strip()

    # Try phone search first (starts with + or is digits)
    if query.startswith("+") or query.isdigit():
        results = await db.search_by_phone(query)
        kind = "phone"
    else:
        results = await db.search_by_username(query)
        kind = "username"

    if not results:
        await message.reply_text(f"No sessions found matching `{query}`.", quote=True)
        return

    keyboard = build_session_keyboard(results, page=0)
    await message.reply_text(
        f"**🔍 Search Results** ({kind}): `{query}`\nFound {len(results)} account(s):",
        reply_markup=keyboard,
        quote=True,
    )


@Client.on_message(filters.private & admin_filter & filters.command("healthcheck"))
async def healthcheck_command(client: Client, message: Message) -> None:
    # Trigger the same logic as the callback healthcheck
    from handlers.callbacks import run_health_check
    msg = await message.reply_text("🏥 Running health check on all sessions…", quote=True)
    await run_health_check(client, msg)
