# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import logging
import traceback
from pyrogram.types import Message
from pyrogram import Client, filters
from asyncio.exceptions import TimeoutError
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
)
from config import API_ID, API_HASH, ADMIN_ID
from database import db

logger = logging.getLogger("otp_bot.generate")

SESSION_STRING_SIZE = 351


def admin_only(_, __, message: Message) -> bool:  # type: ignore[override]
    return message.from_user is not None and message.from_user.id == ADMIN_ID


admin_filter = filters.create(admin_only)


@Client.on_message(filters.private & admin_filter & ~filters.forwarded & filters.command(["logout"]))
async def logout(client: Client, message: Message) -> None:
    user_data = await db.get_session(message.from_user.id)
    if user_data is None:
        return
    await db.set_session(message.from_user.id, session=None)
    await message.reply("**Logout Successfully** ♦")
    logger.info("Admin logged out user_id=%s", message.from_user.id)


@Client.on_message(filters.private & admin_filter & ~filters.forwarded & filters.command(["login"]))
async def login(bot: Client, message: Message) -> None:
    user_id = int(message.from_user.id)

    user_data = await db.get_session(user_id)
    if user_data is not None:
        await message.reply(
            "**You Are Already Logged In. First /logout Your Old Session. Then Do Login.**"
        )
        return

    phone_number_msg = await bot.ask(
        chat_id=user_id,
        text=(
            "<b>Please send the phone number to add (with country code)</b>\n"
            "<b>Example:</b> <code>+13124562345</code>\n\n"
            "Send /cancel to abort."
        ),
    )
    if phone_number_msg.text == "/cancel":
        return await phone_number_msg.reply("<b>Process cancelled!</b>")

    phone_number = phone_number_msg.text.strip()
    client = Client(":memory:", API_ID, API_HASH)
    await client.connect()
    await phone_number_msg.reply("Sending OTP…")

    try:
        code = await client.send_code(phone_number)
    except PhoneNumberInvalid:
        await phone_number_msg.reply("`PHONE_NUMBER` **is invalid.**")
        await client.disconnect()
        return

    try:
        phone_code_msg = await bot.ask(
            user_id,
            (
                "Please check for an OTP in the official Telegram account. "
                "If you got it, send OTP here after reading the below format.\n\n"
                "If OTP is `12345`, **please send it as** `1 2 3 4 5`.\n\n"
                "Send /cancel to abort."
            ),
            filters=filters.text,
            timeout=600,
        )
    except TimeoutError:
        await bot.send_message(user_id, "**Timed out waiting for OTP.**")
        await client.disconnect()
        return

    if phone_code_msg.text == "/cancel":
        await client.disconnect()
        return await phone_code_msg.reply("<b>Process cancelled!</b>")

    try:
        phone_code = phone_code_msg.text.replace(" ", "")
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await phone_code_msg.reply("**OTP is invalid.**")
        await client.disconnect()
        return
    except PhoneCodeExpired:
        await phone_code_msg.reply("**OTP is expired.**")
        await client.disconnect()
        return
    except SessionPasswordNeeded:
        try:
            two_step_msg = await bot.ask(
                user_id,
                "**Your account has two-step verification enabled. Please provide the password.\n\nSend /cancel to abort.**",
                filters=filters.text,
                timeout=300,
            )
        except TimeoutError:
            await bot.send_message(user_id, "**Timed out waiting for 2FA password.**")
            await client.disconnect()
            return

        if two_step_msg.text == "/cancel":
            await client.disconnect()
            return await two_step_msg.reply("<b>Process cancelled!</b>")

        try:
            await client.check_password(password=two_step_msg.text)
        except PasswordHashInvalid:
            await two_step_msg.reply("**Invalid Password Provided.**")
            await client.disconnect()
            return

    string_session = await client.export_session_string()
    await client.disconnect()

    if len(string_session) < SESSION_STRING_SIZE:
        return await message.reply("<b>Invalid session string generated.</b>")

    try:
        # Store in legacy users collection
        if not await db.is_user_exist(user_id):
            await db.add_user(user_id, message.from_user.first_name or "")
        await db.set_session(user_id, session=string_session)

        # Also store in sessions collection for OTP manager
        username = message.from_user.username or message.from_user.first_name or f"user_{user_id}"
        await db.add_session(
            user_id=user_id,
            user_name=username,
            string_session=string_session,
            phone_number=phone_number,
        )
        logger.info("New session saved for user_id=%s phone=%s", user_id, phone_number)
    except Exception as e:
        return await message.reply_text(f"<b>ERROR SAVING SESSION:</b> `{e}`")

    await bot.send_message(
        user_id,
        "<b>✅ Account Added Successfully!\n\n"
        "Use /getotp to fetch OTPs from this account.\n"
        "If you get AUTH KEY errors, /logout and /login again.</b>",
    )
