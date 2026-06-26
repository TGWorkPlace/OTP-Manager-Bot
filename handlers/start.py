import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from config import ADMIN_ID

logger = logging.getLogger("otp_bot.start")


def admin_only(_, __, message: Message) -> bool:  # type: ignore[override]
    return message.from_user is not None and message.from_user.id == ADMIN_ID


admin_filter = filters.create(admin_only)


@Client.on_message(filters.private & admin_filter & filters.command("start"))
async def start_handler(client: Client, message: Message) -> None:
    await message.reply_text(
        "**🔐 OTP Manager Bot**\n\n"
        "**Commands:**\n"
        "/getotp — Show saved accounts & fetch OTPs\n"
        "/stats — Session statistics\n"
        "/healthcheck — Check all sessions\n"
        "/search `<query>` — Search by phone or username\n\n"
        "_Only the configured admin can use this bot._",
        quote=True,
    )
    logger.info("Admin /start")
