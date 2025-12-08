"""
Freya Trades Signal Bot
-----------------------
Simple bot that forwards all messages from source channel to website API.
The website API handles validation, parsing, and storage.

Deploy on: Railway, Render, Fly.io, DigitalOcean, or any VPS

Requirements:
    pip install python-telegram-bot>=21.0 requests python-dotenv

Environment Variables:
    TELEGRAM_BOT_TOKEN=your_bot_token
    TELEGRAM_SOURCE_CHANNEL_ID=-1003232273065
    WEBSITE_API_URL=https://your-site.azurewebsites.net
    INGEST_API_KEY=your_secret_key
"""

import os
import asyncio
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
SOURCE_CHANNEL_ID = os.getenv('TELEGRAM_SOURCE_CHANNEL_ID', '')
WEBSITE_API_URL = os.getenv('WEBSITE_API_URL', 'http://localhost:3000')
INGEST_API_KEY = os.getenv('INGEST_API_KEY', '')
ADMIN_USER_ID = os.getenv('ADMIN_TELEGRAM_USER_ID')

# Validate configuration
if not BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN is required!")
    print("   Get it from @BotFather on Telegram")
    exit(1)

if not INGEST_API_KEY:
    print("❌ ERROR: INGEST_API_KEY is required!")
    exit(1)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Statistics
stats = {
    'messages_received': 0,
    'messages_forwarded': 0,
    'messages_ignored': 0,
    'errors': 0,
    'started_at': datetime.now().isoformat()
}

# Runtime toggle for forwarding
forwarding_enabled = True


def forward_to_website(message_text: str) -> dict:
    """
    Forward message to website API.
    The API will validate, parse, and store if valid.
    """
    try:
        url = f"{WEBSITE_API_URL}/api/signals/ingest"
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {INGEST_API_KEY}'
        }
        payload = {'message': message_text}
        
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        data = response.json()
        
        return {
            'success': response.status_code == 200,
            'status': data.get('status', 'unknown'),
            'data': data
        }
    except requests.exceptions.Timeout:
        logger.error("❌ API request timed out")
        return {'success': False, 'status': 'timeout', 'data': None}
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ API request failed: {e}")
        return {'success': False, 'status': 'error', 'data': None}
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        return {'success': False, 'status': 'error', 'data': None}


def is_from_source_channel(chat_id: int) -> bool:
    """Check if message is from the configured source channel."""
    if not SOURCE_CHANNEL_ID:
        return True  # Accept all if no channel configured
    
    source_id = SOURCE_CHANNEL_ID.replace('-100', '')
    chat_str = str(chat_id).replace('-100', '')
    
    return chat_str == source_id


def is_admin(update: Update) -> bool:
    """Return True if the sender matches ADMIN_USER_ID."""
    if not ADMIN_USER_ID:
        return False
    user = update.effective_user
    return user is not None and str(user.id) == str(ADMIN_USER_ID)


async def require_admin(update: Update) -> bool:
    """Send a rejection message if sender is not admin."""
    if not is_admin(update):
        if update.message:
            await update.message.reply_text("🚫 You are not allowed to use this command.")
        return False
    return True


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages."""
    if not forwarding_enabled:
        return  # forwarding disabled via command

    stats['messages_received'] += 1
    
    # Get message text
    message = update.effective_message
    if not message or not message.text:
        stats['messages_ignored'] += 1
        return
    
    text = message.text.strip()
    
    # Check if from source channel
    chat_id = update.effective_chat.id if update.effective_chat else 0
    
    if not is_from_source_channel(chat_id):
        # Check if it's a forwarded message from source
        if hasattr(message, 'forward_from_chat') and message.forward_from_chat:
            if not is_from_source_channel(message.forward_from_chat.id):
                stats['messages_ignored'] += 1
                return
        else:
            stats['messages_ignored'] += 1
            return
    
    # Forward to website API
    logger.info(f"📤 Forwarding message ({len(text)} chars)")
    result = forward_to_website(text)
    
    if result['success']:
        if result['status'] == 'success':
            stats['messages_forwarded'] += 1
            signal_info = result['data'].get('signal', {})
            script = signal_info.get('script', 'Update')
            logger.info(f"✅ Signal forwarded: {script}")
        elif result['status'] == 'ignored':
            stats['messages_ignored'] += 1
            logger.info(f"⏭️ Message ignored by API (not a valid signal)")
        else:
            stats['messages_ignored'] += 1
            logger.info(f"⏭️ API response: {result['status']}")
    else:
        stats['errors'] += 1
        logger.error(f"❌ Failed to forward: {result['status']}")
    
    # Log stats every 10 messages
    if stats['messages_received'] % 10 == 0:
        logger.info(f"📊 Stats: {stats['messages_received']} received, "
                   f"{stats['messages_forwarded']} forwarded, "
                   f"{stats['messages_ignored']} ignored, "
                   f"{stats['errors']} errors")


async def handle_channel_post(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle channel posts (when bot is added to channel)."""
    await handle_message(update, context)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not await require_admin(update):
        return

    await update.message.reply_text(
        f"🤖 Freya Trades Signal Bot\n\n"
        f"I forward trading signals to the website.\n\n"
        f"📊 Current Stats:\n"
        f"• Messages received: {stats['messages_received']}\n"
        f"• Signals forwarded: {stats['messages_forwarded']}\n"
        f"• Messages ignored: {stats['messages_ignored']}\n"
        f"• Errors: {stats['errors']}\n\n"
        f"📡 API: {WEBSITE_API_URL}\n"
        f"📺 Source: {SOURCE_CHANNEL_ID or 'Any'}\n\n"
        f"Use /stats for statistics\n"
        f"Use /test to send a test signal"
    )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stats command."""
    if not await require_admin(update):
        return

    await update.message.reply_text(
        f"📊 Bot Statistics\n\n"
        f"Messages received: {stats['messages_received']}\n"
        f"Signals forwarded: {stats['messages_forwarded']}\n"
        f"Messages ignored: {stats['messages_ignored']}\n"
        f"Errors: {stats['errors']}\n\n"
        f"Running since: {stats['started_at']}\n"
        f"API URL: {WEBSITE_API_URL}"
    )


async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /test command - send a test signal."""
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

    await update.message.reply_text("🧪 Sending test signal...")
    
    result = forward_to_website(test_message)
    
    if result['success'] and result['status'] == 'success':
        await update.message.reply_text("✅ Test signal forwarded successfully!")
    else:
        await update.message.reply_text(f"❌ Test failed: {result['status']}")


async def health_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /health command - check API connection."""
    if not await require_admin(update):
        return

    await update.message.reply_text("🔍 Checking API connection...")
    
    try:
        url = f"{WEBSITE_API_URL}/api/health"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            await update.message.reply_text(
                f"✅ API is healthy!\n\n"
                f"Status: {data.get('status', 'unknown')}\n"
                f"Database: {data.get('database', {}).get('connectionString', 'unknown')}"
            )
        else:
            await update.message.reply_text(f"⚠️ API returned: {response.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ Cannot reach API: {str(e)}")


async def forward_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Enable forwarding (admin only)."""
    global forwarding_enabled
    if not await require_admin(update):
        return
    forwarding_enabled = True
    await update.message.reply_text("🟢 Forwarding enabled")


async def forward_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Disable forwarding (admin only)."""
    global forwarding_enabled
    if not await require_admin(update):
        return
    forwarding_enabled = False
    await update.message.reply_text("🔴 Forwarding disabled")


async def forward_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Report forwarding status (admin only)."""
    if not await require_admin(update):
        return
    status = "🟢 ON" if forwarding_enabled else "🔴 OFF"
    await update.message.reply_text(f"Forwarding is {status}")


def main():
    """Start the bot."""
    print("=" * 50)
    print("🚀 Freya Trades Signal Bot")
    print("=" * 50)
    print(f"📡 API URL: {WEBSITE_API_URL}")
    print(f"📺 Source Channel: {SOURCE_CHANNEL_ID or 'Any channel'}")
    print(f"🔑 Ingest Key: {INGEST_API_KEY[:8]}..." if INGEST_API_KEY else "❌ No key!")
    print("=" * 50)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("test", test_command))
    application.add_handler(CommandHandler("health", health_command))
    application.add_handler(CommandHandler("forward_on", forward_on_command))
    application.add_handler(CommandHandler("forward_off", forward_off_command))
    application.add_handler(CommandHandler("forward_status", forward_status_command))
    
    # Handle all text messages (from any chat including channels)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Handle channel posts specifically
    application.add_handler(MessageHandler(filters.ChatType.CHANNEL, handle_channel_post))
    
    print("\n✅ Bot is running!")
    print("💡 Commands: /start, /stats, /test, /health")
    print("\nPress Ctrl+C to stop\n")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

