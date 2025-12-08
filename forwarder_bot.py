# forwarder_bot.py
"""
Telegram Bot: Control & Monitoring for Freya/Whop Forwarding

Features:
- /start          → show info & basic stats
- /stats          → show stats
- /test           → send sample signal to Freya ingest API
- /health         → check Freya API health endpoint
- /forward_on     → enable forwarding (writes forward_state.json)
- /forward_off    → disable forwarding
- /forward_status → show forwarding state

Reads config from environment (.env):
    BOT_TOKEN
    WEBSITE_API_URL
    INGEST_API_KEY
    LOG_LEVEL
"""

import os
import json
import logging
from datetime import datetime

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# ---------------------------------------------------------------------------
# Environment & logging
# ---------------------------------------------------------------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBSITE_API_URL = os.getenv("WEBSITE_API_URL", "").strip()
INGEST_API_KEY = os.getenv("INGEST_API_KEY", "").strip()
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

FORWARD_STATE_FILE = "forward_state.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger("forwarder_bot")

if not BOT_TOKEN:
    raise SystemExit("❌ BOT_TOKEN is required in .env")

# ---------------------------------------------------------------------------
# Shared forwarding state helpers (used by this bot AND user_forwarder.py)
# ---------------------------------------------------------------------------


def _read_forward_state() -> bool:
    """Read forwarding state from JSON file. Default: True (enabled)."""
    try:
        with open(FORWARD_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return bool(data.get("enabled", True))
    except FileNotFoundError:
        return True
    except Exception as exc:
        logger.warning("Could not read %s: %s", FORWARD_STATE_FILE, exc)
        return True


def _write_forward_state(enabled: bool) -> None:
    """Write forwarding state to JSON file."""
    try:
        with open(FORWARD_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"enabled": bool(enabled)}, f)
    except Exception as exc:
        logger.error("Could not write %s: %s", FORWARD_STATE_FILE, exc)


def is_forwarding_enabled() -> bool:
    return _read_forward_state()


def set_forwarding_enabled(value: bool) -> None:
    _write_forward_state(value)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

stats = {
    "started_at": datetime.now().isoformat(timespec="seconds"),
    "commands_used": 0,
    "tests_run": 0,
    "health_checks": 0,
}


def _inc_stat(key: str) -> None:
    stats[key] = stats.get(key, 0) + 1


# ---------------------------------------------------------------------------
# Admin check (optional – here we allow everyone, but you can restrict)
# ---------------------------------------------------------------------------

ADMIN_IDS = set(
    int(x.strip()) for x in os.getenv("APPROVER_IDS", "").split(",") if x.strip()
)


def is_admin(update: Update) -> bool:
    if not ADMIN_IDS:
        # If no admins set, allow anyone (or you can flip this to False)
        return True
    user = update.effective_user
    return user is not None and user.id in ADMIN_IDS


async def require_admin(update: Update) -> bool:
    if not is_admin(update):
        if update.message:
            await update.message.reply_text("🚫 You are not allowed to use this command.")
        return False
    return True


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _inc_stat("commands_used")
    if not await require_admin(update):
        return

    enabled = "🟢 ON" if is_forwarding_enabled() else "🔴 OFF"

    await update.message.reply_text(
        f"🤖 Freya/Whop Forwarder Control Bot\n\n"
        f"Forwarding status: {enabled}\n\n"
        f"📡 Freya API: {WEBSITE_API_URL or 'not configured'}\n"
        f"🔐 Ingest key set: {'yes' if INGEST_API_KEY else 'no'}\n\n"
        f"Commands:\n"
        f"• /stats – show stats\n"
        f"• /test – send a test signal to Freya\n"
        f"• /health – check Freya API health\n"
        f"• /forward_on – enable forwarding\n"
        f"• /forward_off – disable forwarding\n"
        f"• /forward_status – show forwarding status"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _inc_stat("commands_used")
    if not await require_admin(update):
        return

    enabled = "ON" if is_forwarding_enabled() else "OFF"

    await update.message.reply_text(
        f"📊 Bot Stats\n\n"
        f"Started at: {stats['started_at']}\n"
        f"Commands used: {stats.get('commands_used', 0)}\n"
        f"Tests run: {stats.get('tests_run', 0)}\n"
        f"Health checks: {stats.get('health_checks', 0)}\n"
        f"Forwarding: {enabled}"
    )


async def forward_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _inc_stat("commands_used")
    if not await require_admin(update):
        return
    set_forwarding_enabled(True)
    await update.message.reply_text("🟢 Forwarding enabled (saved to forward_state.json)")


async def forward_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _inc_stat("commands_used")
    if not await require_admin(update):
        return
    set_forwarding_enabled(False)
    await update.message.reply_text("🔴 Forwarding disabled (saved to forward_state.json)")


async def forward_status_command(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    _inc_stat("commands_used")
    if not await require_admin(update):
        return
    status = "🟢 ON" if is_forwarding_enabled() else "🔴 OFF"
    await update.message.reply_text(f"Forwarding is {status}")


# ---------------------------------------------------------------------------
# Freya API helpers
# ---------------------------------------------------------------------------


def _call_ingest_sync(message_text: str) -> dict:
    if not WEBSITE_API_URL or not INGEST_API_KEY:
        return {"success": False, "status": "not_configured", "data": None}

    url = WEBSITE_API_URL.rstrip("/") + "/api/signals/ingest"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {INGEST_API_KEY}",
    }
    payload = {"message": message_text}
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        try:
            data = resp.json()
        except ValueError:
            data = {"raw_text": resp.text[:200]}
        return {
            "success": resp.status_code == 200,
            "status": data.get("status", "unknown"),
            "data": data,
        }
    except Exception as exc:
        logger.exception("Ingest call failed: %s", exc)
        return {"success": False, "status": "error", "data": None}


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _inc_stat("commands_used")
    _inc_stat("tests_run")
    if not await require_admin(update):
        return

    test_message = """script          : BTCUSD
Position        : BUY ⬆️
Enter Price     : 90827.56
Take Profit 1   : 91528.57
Take Profit 2   : 91995.90
Take Profit 3   : 92696.91
Take Profit 4   : 93631.58
Stoploss        : 89659.22"""

    await update.message.reply_text("🧪 Sending test signal to Freya ingest...")

    result = await context.application.run_in_threadpool(
        _call_ingest_sync, test_message
    )

    if result["success"] and result["status"] == "success":
        await update.message.reply_text("✅ Test signal processed successfully by Freya!")
    else:
        await update.message.reply_text(
            f"⚠️ Test call finished.\n"
            f"Success: {result['success']}\n"
            f"Status: {result['status']}"
        )


def _health_check_sync() -> tuple[bool, int | None, dict | None]:
    if not WEBSITE_API_URL:
        return False, None, None
    url = WEBSITE_API_URL.rstrip("/") + "/api/health"
    try:
        resp = requests.get(url, timeout=5)
        try:
            data = resp.json()
        except ValueError:
            data = None
        return resp.status_code == 200, resp.status_code, data
    except Exception as exc:
        logger.exception("Health check failed: %s", exc)
        return False, None, None


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _inc_stat("commands_used")
    _inc_stat("health_checks")
    if not await require_admin(update):
        return

    await update.message.reply_text("🔍 Checking Freya API health...")

    ok, status_code, data = await context.application.run_in_threadpool(
        _health_check_sync
        )
    if ok:
        status = (data or {}).get("status", "unknown")
        db_status = (data or {}).get("database", {}).get("status", "unknown")
        await update.message.reply_text(
            f"✅ API is healthy!\n\nStatus: {status}\nDatabase: {db_status}"
        )
    else:
        if status_code is None:
            await update.message.reply_text("❌ Could not reach Freya API.")
        else:
            await update.message.reply_text(
                f"⚠️ API responded with status code: {status_code}"
            )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 60)
    print("🚀 forwarder_bot.py (control bot)")
    print("=" * 60)
    print(f"📡 Freya API URL: {WEBSITE_API_URL or 'not configured'}")
    print(f"🔐 Ingest key set: {'yes' if INGEST_API_KEY else 'no'}")
    print(f"📝 Log level: {LOG_LEVEL}")
    print("=" * 60)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("test", test_command))
    app.add_handler(CommandHandler("health", health_command))
    app.add_handler(CommandHandler("forward_on", forward_on_command))
    app.add_handler(CommandHandler("forward_off", forward_off_command))
    app.add_handler(CommandHandler("forward_status", forward_status_command))

    print("\n✅ Bot is running (forwarder_bot.py)")
    print("💡 Commands: /start, /stats, /test, /health, /forward_on, /forward_off, /forward_status\n")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
