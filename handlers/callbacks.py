from __future__ import annotations

import asyncio
import logging
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, Message

from config import ADMIN_ID, OTP_AUTO_DELETE
from database import db
from utils.otp import fetch_otp_from_session
from utils.paginator import build_otp_keyboard, build_session_keyboard

logger = logging.getLogger("otp_bot.callbacks")

# In-memory page cache: {admin_message_id: page_number}
_page_cache: dict[int, int] = {}


def admin_cb(_, __, cb: CallbackQuery) -> bool:  # type: ignore[override]
    return cb.from_user is not None and cb.from_user.id == ADMIN_ID


admin_cb_filter = filters.create(admin_cb)


@Client.on_callback_query(admin_cb_filter)
async def callback_handler(client: Client, cb: CallbackQuery) -> None:
    await cb.answer()
    data: str = cb.data or ""

    if data == "noop":
        return

    if data.startswith("otp:"):
        session_id = data.split(":", 1)[1]
        await _handle_otp_fetch(client, cb, session_id, is_refresh=False)

    elif data.startswith("refresh:"):
        session_id = data.split(":", 1)[1]
        await _handle_otp_fetch(client, cb, session_id, is_refresh=True)

    elif data.startswith("page:"):
        page = int(data.split(":", 1)[1])
        await _handle_page(client, cb, page)

    elif data == "back:list":
        await _handle_page(client, cb, page=0)

    elif data == "stats":
        await _handle_stats(client, cb)

    elif data == "healthcheck":
        await _handle_health_check_cb(client, cb)

    elif data.startswith("search:"):
        kind = data.split(":", 1)[1]
        await _handle_search_prompt(client, cb, kind)

    else:
        logger.warning("Unknown callback data: %s", data)


# ──────────────────────────────────────────────────────────────
# OTP Fetch
# ──────────────────────────────────────────────────────────────

async def _handle_otp_fetch(
    client: Client,
    cb: CallbackQuery,
    session_id: str,
    is_refresh: bool,
) -> None:
    loading_text = "🔄 Fetching OTP, please wait…"
    try:
        await cb.edit_message_text(loading_text)
    except Exception:
        pass

    session_doc = await db.get_session_by_id(session_id)
    if not session_doc:
        await cb.edit_message_text("❌ Session not found in database.")
        return

    name = session_doc.get("user_name") or "Unknown"
    phone = session_doc.get("phone_number", "")
    last_msg_id = session_doc.get("last_message_id")

    result = await fetch_otp_from_session(
        session_doc["string_session"],
        last_message_id=last_msg_id,
    )

    # Mark dead sessions
    if result.get("dead"):
        await db.update_session_status(session_id, "dead")
        await cb.edit_message_text(
            f"💀 **Session Dead**\n\n"
            f"Account: `{name}` ({phone})\n"
            f"Error: {result['error']}\n\n"
            "_This session has been marked as dead._",
            reply_markup=build_otp_keyboard(session_id),
        )
        return

    if not result["success"]:
        await cb.edit_message_text(
            f"⚠️ **Error Fetching OTP**\n\n"
            f"Account: `{name}` ({phone})\n"
            f"Error: {result['error']}",
            reply_markup=build_otp_keyboard(session_id),
        )
        return

    # No message found
    if result["message_text"] is None:
        await cb.edit_message_text(
            f"📭 **No Messages Found**\n\nAccount: `{name}` ({phone})",
            reply_markup=build_otp_keyboard(session_id),
        )
        return

    # No new message since last check
    if not result["is_new"] and last_msg_id is not None:
        date_str = _fmt_date(result["date"])
        await cb.edit_message_text(
            f"ℹ️ **No New OTP Since Last Check**\n\n"
            f"Account: `{name}` ({phone})\n"
            f"Last checked message is still the latest.\n"
            f"Time: `{date_str}`",
            reply_markup=build_otp_keyboard(session_id),
        )
        return

    # Update DB
    await db.update_last_checked(session_id, result["message_id"])
    await db.update_session_status(session_id, "active")

    date_str = _fmt_date(result["date"])
    otp_line = f"`{result['otp']}`" if result["otp"] else "_Could not extract numeric OTP_"

    response_text = (
        f"**Account:**\n`{name}` ({phone})\n\n"
        f"**Latest OTP:**\n{otp_line}\n\n"
        f"**Full Message:**\n```{result['message_text']}```\n\n"
        f"**Time:** `{date_str}`"
    )

    msg = await cb.edit_message_text(
        response_text,
        reply_markup=build_otp_keyboard(session_id),
    )

    # Auto-delete if configured
    if OTP_AUTO_DELETE > 0 and msg:
        asyncio.create_task(_auto_delete(client, cb.message.chat.id, msg.id, OTP_AUTO_DELETE))

    logger.info("OTP fetched for session_id=%s name=%s", session_id, name)


# ──────────────────────────────────────────────────────────────
# Pagination
# ──────────────────────────────────────────────────────────────

async def _handle_page(client: Client, cb: CallbackQuery, page: int) -> None:
    sessions = await db.get_all_sessions()
    keyboard = build_session_keyboard(sessions, page=page)
    await cb.edit_message_text(
        f"**📋 Saved Accounts** — {len(sessions)} total\n\nSelect an account to fetch OTP:",
        reply_markup=keyboard,
    )


# ──────────────────────────────────────────────────────────────
# Stats
# ──────────────────────────────────────────────────────────────

async def _handle_stats(client: Client, cb: CallbackQuery) -> None:
    counts = await db.count_sessions()
    last_time = await db.get_last_otp_time()
    last_str = last_time.strftime("%Y-%m-%d %H:%M UTC") if last_time else "Never"

    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await cb.edit_message_text(
        "**📊 Session Statistics**\n\n"
        f"Total Sessions: `{counts['total']}`\n"
        f"✅ Active: `{counts['active']}`\n"
        f"❌ Invalid: `{counts['invalid']}`\n"
        f"💀 Dead: `{counts['dead']}`\n"
        f"🕐 Last OTP Check: `{last_str}`",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀ Back", callback_data="back:list")]]
        ),
    )


# ──────────────────────────────────────────────────────────────
# Health Check
# ──────────────────────────────────────────────────────────────

async def _handle_health_check_cb(client: Client, cb: CallbackQuery) -> None:
    await cb.edit_message_text("🏥 Running health check on all sessions…")
    await run_health_check(client, cb.message)


async def run_health_check(client: Client, msg: Message) -> None:
    sessions = await db.get_all_sessions()
    if not sessions:
        await msg.edit_text("No sessions to check.")
        return

    ok, dead, err = 0, 0, 0
    for s in sessions:
        result = await fetch_otp_from_session(s["string_session"])
        sid = str(s["_id"])
        if result.get("dead"):
            await db.update_session_status(sid, "dead")
            dead += 1
            logger.warning("Health check: dead session %s", sid)
        elif result["success"]:
            await db.update_session_status(sid, "active")
            ok += 1
        else:
            err += 1

    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await msg.edit_text(
        f"🏥 **Health Check Complete**\n\n"
        f"✅ Active: `{ok}`\n"
        f"💀 Dead: `{dead}`\n"
        f"⚠️ Errors: `{err}`\n"
        f"Total checked: `{len(sessions)}`",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("◀ Back", callback_data="back:list")]]
        ),
    )
    logger.info("Health check done — ok=%d dead=%d err=%d", ok, dead, err)


# ──────────────────────────────────────────────────────────────
# Search prompt (inline flow)
# ──────────────────────────────────────────────────────────────

async def _handle_search_prompt(client: Client, cb: CallbackQuery, kind: str) -> None:
    from pyrogram.types import ForceReply
    label = "phone number (e.g. +91...)" if kind == "phone" else "username"
    await cb.message.reply_text(
        f"Send the {label} to search:",
        reply_markup=ForceReply(selective=True),
    )


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _fmt_date(dt) -> str:
    if dt is None:
        return "Unknown"
    try:
        return dt.strftime("%I:%M %p, %d %b %Y")
    except Exception:
        return str(dt)


async def _auto_delete(client: Client, chat_id: int, message_id: int, delay: int) -> None:
    await asyncio.sleep(delay)
    try:
        await client.delete_messages(chat_id, message_id)
        logger.info("Auto-deleted OTP message %d after %ds", message_id, delay)
    except Exception as e:
        logger.warning("Auto-delete failed: %s", e)
