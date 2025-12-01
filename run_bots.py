"""
Launcher script that runs both forwarder_bot.py and user_forwarder.py concurrently.

Usage:
    python run_bots.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
from multiprocessing import Process

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger("launcher")


def run_forwarder_bot():
    """Run the Telegram bot (forwarder_bot.py)."""
    import forwarder_bot

    try:
        forwarder_bot.main()
    except KeyboardInterrupt:
        logger.info("Forwarder bot stopped.")
    except Exception as exc:
        logger.exception("Forwarder bot crashed: %s", exc)


def run_user_forwarder():
    """Run the userbot (user_forwarder.py)."""
    import user_forwarder

    try:
        asyncio.run(user_forwarder.main())
    except KeyboardInterrupt:
        logger.info("User forwarder stopped.")
    except Exception as exc:
        logger.exception("User forwarder crashed: %s", exc)


def main():
    """Launch both bots concurrently."""
    logger.info("Starting both bots...")

    # Start forwarder_bot in a separate process
    bot_process = Process(target=run_forwarder_bot, name="ForwarderBot")
    bot_process.start()
    logger.info("Forwarder bot process started (PID: %s)", bot_process.pid)

    # Start user_forwarder in a separate process
    userbot_process = Process(target=run_user_forwarder, name="UserForwarder")
    userbot_process.start()
    logger.info("User forwarder process started (PID: %s)", userbot_process.pid)

    def signal_handler(sig, frame):
        logger.info("Shutting down both bots...")
        bot_process.terminate()
        userbot_process.terminate()
        bot_process.join(timeout=5)
        userbot_process.join(timeout=5)
        if bot_process.is_alive():
            logger.warning("Force killing forwarder bot process...")
            bot_process.kill()
        if userbot_process.is_alive():
            logger.warning("Force killing user forwarder process...")
            userbot_process.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Wait for both processes
        bot_process.join()
        userbot_process.join()
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()

