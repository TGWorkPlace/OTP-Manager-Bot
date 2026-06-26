"""
bot.py
------
• Creates the Pyrogram Bot client.
• Starts an aiohttp web server on PORT (default 8080) for Koyeb health checks.
• Web routes:
    GET /          → health check (200 OK)
    GET /ping      → 200 "pong"
    GET /restart   → gracefully restarts the bot process
• Imports all handler modules so their decorators register on the client.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from aiohttp import web
from pyrogram import Client, idle

from config import API_ID, API_HASH, BOT_TOKEN, PORT
from utils.logger import setup_logger

setup_logger()
logger = logging.getLogger("otp_bot.bot")

# ──────────────────────────────────────────────
# Pyrogram Client
# ──────────────────────────────────────────────

bot = Client(
    name="otp_manager_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    plugins=dict(root="handlers"),  # auto-loads handlers/
)

# Also register generate.py handlers
import generate  # noqa: F401  (side-effect: registers decorators)


# ──────────────────────────────────────────────
# aiohttp Web Server
# ──────────────────────────────────────────────

async def health(_: web.Request) -> web.Response:
    return web.Response(text="OK", status=200)


async def ping(_: web.Request) -> web.Response:
    return web.Response(text="pong", status=200)


async def restart(_: web.Request) -> web.Response:
    """Trigger a graceful restart by re-execing the current process."""
    logger.warning("Restart requested via /restart endpoint")

    async def _do_restart() -> None:
        await asyncio.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)

    asyncio.create_task(_do_restart())
    return web.Response(text="Restarting…", status=200)


def build_web_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/ping", ping)
    app.router.add_get("/restart", restart)
    return app


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────

async def main() -> None:
    # Start the web server
    web_app = build_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Web server started on port %d", PORT)

    # Start Pyrogram
    await bot.start()
    logger.info("Bot started — @%s", (await bot.get_me()).username)

    await idle()

    await bot.stop()
    await runner.cleanup()
    logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
