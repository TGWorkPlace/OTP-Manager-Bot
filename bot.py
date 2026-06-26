from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from aiohttp import web
from pyrogram import Client

from config import API_ID, API_HASH, BOT_TOKEN, PORT
from utils.logger import setup_logger

setup_logger()
logger = logging.getLogger("otp_bot.bot")

# ──────────────────────────────────────────────
# Pyrogram Client (NO plugins= here)
# ──────────────────────────────────────────────

bot = Client(
    name="otp_manager_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# Manually import every handler module AFTER bot is defined.
# @Client.on_* decorators register on the class, so importing
# the modules here is enough — no plugins= magic needed.
import handlers.start      # noqa: F401, E402
import handlers.getotp     # noqa: F401, E402
import handlers.callbacks  # noqa: F401, E402
import generate            # noqa: F401, E402


# ──────────────────────────────────────────────
# aiohttp Web Server
# ──────────────────────────────────────────────

async def health(_: web.Request) -> web.Response:
    return web.Response(text="OK", status=200)


async def ping(_: web.Request) -> web.Response:
    return web.Response(text="pong", status=200)


async def restart(_: web.Request) -> web.Response:
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
    # Start aiohttp
    web_app = build_web_app()
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Web server started on port %d", PORT)

    # Start Pyrogram
    await bot.start()
    me = await bot.get_me()
    logger.info("Bot started — @%s", me.username)

    # Keep alive: wait for SIGTERM / SIGINT instead of pyrogram.idle()
    # so aiohttp stays responsive in the same event loop.
    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    await stop_event.wait()

    # Graceful shutdown
    await bot.stop()
    await runner.cleanup()
    logger.info("Bot stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
