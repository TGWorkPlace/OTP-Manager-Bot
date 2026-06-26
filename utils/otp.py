from __future__ import annotations

import asyncio
import re
import logging
from typing import Optional

from pyrogram import Client
from pyrogram.errors import (
    AuthKeyUnregistered,
    UserDeactivated,
    SessionRevoked,
    FloodWait,
    RPCError,
)

from config import API_ID, API_HASH

logger = logging.getLogger("otp_bot.otp")

TELEGRAM_OFFICIAL_ID = 777000

OTP_PATTERNS = [
    r"(?:login|confirmation|verification|two-step verification|telegram)\s*code[:\s]+(\d{4,8})",
    r"your\s+(?:login\s+)?code[:\s]+(\d{4,8})",
    r"\b(\d{4,8})\b",  # fallback: any 4-8 digit number
]

KEYWORD_TRIGGERS = [
    "login code",
    "telegram code",
    "confirmation code",
    "two-step verification",
    "your code",
    "verification code",
]


def extract_otp(text: str) -> Optional[str]:
    """Extract OTP from a Telegram message string."""
    lower = text.lower()
    is_otp_msg = any(kw in lower for kw in KEYWORD_TRIGGERS)
    if not is_otp_msg:
        return None

    for pattern in OTP_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


async def fetch_otp_from_session(
    string_session: str,
    last_message_id: Optional[int] = None,
) -> dict:
    """
    Connect with a string session, fetch the latest message from 777000.

    Returns:
        {
            "success": bool,
            "otp": str | None,
            "message_text": str | None,
            "message_id": int | None,
            "date": datetime | None,
            "is_new": bool,
            "error": str | None,
            "dead": bool,   # True = session is permanently invalid
        }
    """
    result: dict = {
        "success": False,
        "otp": None,
        "message_text": None,
        "message_id": None,
        "date": None,
        "is_new": False,
        "error": None,
        "dead": False,
    }

    client = Client(
        name=":memory:",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=string_session,
        no_updates=True,
    )

    try:
        await client.connect()

        messages = await client.get_messages(
            chat_id=TELEGRAM_OFFICIAL_ID,
            limit=1,
        )

        if not messages or (isinstance(messages, list) and len(messages) == 0):
            result["success"] = True
            result["error"] = "No messages found from Telegram."
            return result

        msg = messages[0] if isinstance(messages, list) else messages
        if msg is None or msg.empty:
            result["success"] = True
            result["error"] = "No messages found from Telegram."
            return result

        result["message_id"] = msg.id
        result["message_text"] = msg.text or msg.caption or ""
        result["date"] = msg.date
        result["otp"] = extract_otp(result["message_text"])
        result["success"] = True

        if last_message_id is not None and msg.id <= last_message_id:
            result["is_new"] = False
        else:
            result["is_new"] = True

    except FloodWait as e:
        result["error"] = f"FloodWait: retry after {e.value}s"
        logger.warning("FloodWait %ss for session", e.value)
    except (AuthKeyUnregistered, SessionRevoked, UserDeactivated) as e:
        result["error"] = f"Session dead: {type(e).__name__}"
        result["dead"] = True
        logger.warning("Dead session: %s", type(e).__name__)
    except RPCError as e:
        result["error"] = f"RPC error: {e}"
        logger.error("RPCError: %s", e)
    except Exception as e:
        result["error"] = f"Unexpected error: {e}"
        logger.exception("Unexpected error fetching OTP")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass

    return result
