"""
Telethon-based userbot that watches a source channel, forwards messages to your group,
and auto-forwards to Whop or requests approval via bot.

Usage:
    1. pip install telethon python-dotenv requests
    2. Fill in .env with:
        API_ID=123456
        API_HASH=your_api_hash
        USERBOT_SESSION=user_forwarder  # optional session file name
        SOURCE_CHANNEL=@wazirforexalerts  # channel username or ID to watch
        FORWARD_TO_CHAT_ID=-1001234567890  # destination supergroup id
        FORWARD_TO_THREAD_ID=7              # forum topic id
        BOT_TOKEN=...                       # bot token for approval requests
        WHOP_WEBHOOK_URL=...                # optional override; falls back to WEBHOOK_URL
    3. Run: python user_forwarder.py
    4. Follow the login prompt (code sent by Telegram).
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
from typing import Optional, Tuple, Union, Dict

import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.functions.channels import JoinChannelRequest

import forwarder_bot as formatter

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("USERBOT_SESSION", "user_forwarder")

SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL")  # Channel username or ID
FORWARD_TO_CHAT_ID_RAW = os.getenv("FORWARD_TO_CHAT_ID")
FORWARD_TO_THREAD_ID_RAW = os.getenv("FORWARD_TO_THREAD_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not API_ID or not API_HASH:
    raise RuntimeError("API_ID and API_HASH must be set in .env (obtain from my.telegram.org).")

if not SOURCE_CHANNEL:
    raise RuntimeError("SOURCE_CHANNEL must be set in .env (e.g., @wazirforexalerts).")

if not FORWARD_TO_CHAT_ID_RAW:
    raise RuntimeError("FORWARD_TO_CHAT_ID must be set in .env (destination group ID).")

def convert_to_bot_api_id(telethon_id: int) -> int:
    """
    Convert Telethon ID to Bot API format.
    For supergroups/channels: -100 + ID
    For regular groups: -ID
    For channels: -100 + ID
    """
    if telethon_id > 0:
        # Positive ID means it's a supergroup/channel, convert to -100xxxxxxxxxx format
        return int(f"-100{telethon_id}")
    # Already negative, return as-is
    return telethon_id

FORWARD_TO_CHAT_ID_RAW_INT = int(FORWARD_TO_CHAT_ID_RAW)
# Convert to Bot API format if it's a positive ID (Telethon format)
if FORWARD_TO_CHAT_ID_RAW_INT > 0:
    FORWARD_TO_CHAT_ID: int = convert_to_bot_api_id(FORWARD_TO_CHAT_ID_RAW_INT)
else:
    FORWARD_TO_CHAT_ID: int = FORWARD_TO_CHAT_ID_RAW_INT  # Already in Bot API format

FORWARD_TO_THREAD_ID: Optional[int] = (
    int(FORWARD_TO_THREAD_ID_RAW) if FORWARD_TO_THREAD_ID_RAW else None
)

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN must be set in .env for approval requests.")

# Chat where approval requests should be sent (defaults to destination chat)
# Can be a chat ID (number) or channel username (e.g., @channelname)
APPROVAL_CHAT_ID_RAW = os.getenv("APPROVAL_CHAT_ID")
if APPROVAL_CHAT_ID_RAW:
    # Check if it's a username (starts with @) or numeric ID
    if APPROVAL_CHAT_ID_RAW.strip().startswith("@"):
        APPROVAL_CHAT_ID = APPROVAL_CHAT_ID_RAW.strip()  # Keep as username
    else:
        raw_id = int(APPROVAL_CHAT_ID_RAW)
        # Convert to Bot API format if it's a positive ID (Telethon format)
        if raw_id > 0:
            APPROVAL_CHAT_ID = convert_to_bot_api_id(raw_id)
        else:
            APPROVAL_CHAT_ID = raw_id  # Already in Bot API format
else:
    APPROVAL_CHAT_ID = FORWARD_TO_CHAT_ID

WEBHOOK_URL_OVERRIDE = os.getenv("WHOP_WEBHOOK_URL")
if WEBHOOK_URL_OVERRIDE:
    formatter.WEBHOOK_URL = WEBHOOK_URL_OVERRIDE

LOG_LEVEL = os.getenv("USERBOT_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger("user_forwarder")


PayloadType = Union[Dict[str, Optional[str]], str]


def build_formatted_payload(text: str) -> Optional[Tuple[str, PayloadType]]:
    cleaned = formatter.remove_banned(text)
    if not cleaned:
        logger.info("Message cleaned to empty content; skipping.")
        return None

    status_only_override = formatter.is_status_only_message(cleaned)
    if status_only_override:
        formatted_text = cleaned.strip()
    else:
        trade = formatter.parse_trade(cleaned)
        formatted_text = formatter.build_formatted(trade, cleaned)

    payload = formatter.build_webhook_payload(formatted_text, meta=None)
    return formatted_text, payload


def should_auto_forward(cleaned: str, trade: formatter.TradeInfo) -> bool:
    """Check if message matches known formats for auto-forwarding."""
    # Check for status-only messages (Position Status, Take Profit X From..., etc.)
    if formatter.is_status_only_message(cleaned):
        return True
    
    # Also check for status patterns in the text
    lower_cleaned = cleaned.lower()
    status_patterns = [
        "position status",
        "take profit",
        "hit tp",
        "hit sl",
        "from long signal",
        "from short signal",
    ]
    if any(pattern in lower_cleaned for pattern in status_patterns):
        return True

    # Check for full trade format: must have Position AND Enter Price
    has_position = bool(trade.position)
    has_enter = bool(trade.enter)
    
    # Also check text directly for these keywords
    has_position_text = "position" in lower_cleaned
    has_enter_text = "enter price" in lower_cleaned or "enter" in lower_cleaned
    
    # Auto-forward if we have both position and enter (either parsed or in text)
    return (has_position and has_enter) or (has_position_text and has_enter_text)


async def send_approval_request(
    client: TelegramClient, formatted_text: str, original_message_id: int
) -> None:
    """Send approval request via bot to the destination group/topic."""
    import json

    key = f"{FORWARD_TO_CHAT_ID}:{original_message_id}"
    escaped = html.escape(formatted_text)
    preview = f"Ready to forward this message?\n\n<pre>{escaped}</pre>"
    preview = preview[:4000]

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Allow Forward ✅", "callback_data": f"allow|{key}"},
                {"text": "Deny 🚫", "callback_data": f"deny|{key}"},
            ]
        ]
    }

    # Resolve channel username to ID if needed
    approval_chat_id = APPROVAL_CHAT_ID
    if isinstance(APPROVAL_CHAT_ID, str) and APPROVAL_CHAT_ID.startswith("@"):
        # Try to get channel ID from username
        try:
            channel_entity = await client.get_entity(APPROVAL_CHAT_ID)
            telethon_id = channel_entity.id
            # Convert Telethon ID to Bot API format
            approval_chat_id = convert_to_bot_api_id(telethon_id) if telethon_id > 0 else telethon_id
            logger.info(
                "Resolved channel username %s to ID %s (Bot API format: %s)",
                APPROVAL_CHAT_ID,
                telethon_id,
                approval_chat_id,
            )
        except Exception as resolve_exc:
            logger.error(
                "Failed to resolve channel username %s: %s. Trying username directly.",
                APPROVAL_CHAT_ID,
                resolve_exc,
            )
            # Keep the username as-is and let Telegram API handle it
            approval_chat_id = APPROVAL_CHAT_ID

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    params = {
        "chat_id": approval_chat_id,
        "text": preview,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
        "reply_markup": json.dumps(keyboard),
    }
    # Only add thread_id if approval chat is the same as forward chat (and thread_id exists)
    if isinstance(approval_chat_id, int) and approval_chat_id == FORWARD_TO_CHAT_ID and FORWARD_TO_THREAD_ID:
        params["message_thread_id"] = FORWARD_TO_THREAD_ID

    try:
        logger.info(
            "Attempting to send approval request to chat_id=%s (original=%s)",
            approval_chat_id,
            APPROVAL_CHAT_ID,
        )
        response = requests.post(url, json=params, timeout=10)
        response.raise_for_status()
        logger.info(
            "✅ Approval request sent successfully for message id=%s to chat=%s thread=%s",
            original_message_id,
            approval_chat_id,
            FORWARD_TO_THREAD_ID if isinstance(approval_chat_id, int) and approval_chat_id == FORWARD_TO_CHAT_ID else None,
        )
    except Exception as exc:
        logger.exception("❌ Failed to send approval request: %s", exc)
        if 'response' in locals():
            logger.error("Response status: %s", response.status_code)
            logger.error("Response body: %s", response.text)
            try:
                error_data = response.json()
                logger.error("Error details: %s", error_data)
            except:
                pass


async def process_channel_message(event) -> None:
    """Process a message from the source channel: forward to group only if auto-forwardable, then handle Whop."""
    message = event.message
    text = message.message
    logger.info(
        "Processing message id=%s from chat_id=%s, has_text=%s",
        message.id,
        event.chat_id,
        bool(text),
    )
    if text:
        logger.info("Raw message text (first 500 chars): %s", text[:500])
    if not text:
        logger.info("Skipping message id=%s (no text content)", message.id)
        return

    # Step 1: Process for Whop and check if should auto-forward
    result = build_formatted_payload(text)
    if not result:
        logger.info("Skipping message id=%s (cleaned to empty)", message.id)
        return

    formatted_text, payload = result

    # Step 2: Check if should auto-forward or request approval
    cleaned = formatter.remove_banned(text)
    trade = formatter.parse_trade(cleaned)
    auto_forward = should_auto_forward(cleaned, trade)
    
    logger.info(
        "Message id=%s: auto_forward=%s, has_position=%s, has_enter=%s, is_status_only=%s",
        message.id,
        auto_forward,
        bool(trade.position),
        bool(trade.enter),
        formatter.is_status_only_message(cleaned),
    )

    if auto_forward:
        # Step 3a: Auto-forwardable messages → forward to subtopic AND send to Whop
        forwarded_msg = None
        try:
            # Use Bot API to send to topic (supports message_thread_id directly)
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            params = {
                "chat_id": FORWARD_TO_CHAT_ID,
                "text": text,  # Send original text
            }
            if FORWARD_TO_THREAD_ID:
                params["message_thread_id"] = FORWARD_TO_THREAD_ID
            
            response = requests.post(url, json=params, timeout=10)
            response.raise_for_status()
            result = response.json()
            if result.get("ok"):
                forwarded_msg_id = result["result"]["message_id"]
                # Create a mock message object for compatibility
                class MockMessage:
                    def __init__(self, msg_id):
                        self.id = msg_id
                forwarded_msg = MockMessage(forwarded_msg_id)
                
                logger.info(
                    "✅ Sent message id=%s from channel to chat=%s thread=%s (bot API)",
                    message.id,
                    FORWARD_TO_CHAT_ID,
                    FORWARD_TO_THREAD_ID,
                )
            else:
                raise Exception(f"Bot API error: {result.get('description', 'Unknown error')}")
        except Exception as exc:
            logger.exception("Failed to send message to group via bot API: %s", exc)
            # Try fallback: use Telethon to forward (won't go to topic but at least it's forwarded)
            try:
                forwarded_msgs = await event.client.forward_messages(
                    FORWARD_TO_CHAT_ID,
                    message,
                    from_peer=event.chat_id,
                )
                forwarded_msg = forwarded_msgs[0] if forwarded_msgs else None
                logger.warning("Used fallback forward via Telethon (may not be in correct topic)")
            except Exception as fallback_exc:
                logger.exception("Fallback forward also failed: %s", fallback_exc)
                # Continue anyway to try webhook

        # Step 4a: Auto-forward to Whop
        logger.info("Auto-forwarding message id=%s to Whop", message.id)
        logger.info("Formatted text being sent:\n%s", formatted_text)
        logger.info("Payload being sent: %s", payload)
        try:
            response = formatter.post_to_webhook(payload, formatted_text)
        except Exception as exc:
            logger.exception("Webhook post failed: %s", exc)
            logger.info("Falling back to approval request due to webhook error")
            if forwarded_msg:
                await send_approval_request(event.client, formatted_text, forwarded_msg.id)
            return

        logger.info("Webhook response: status=%s, body=%s", response.status_code, response.text[:500])
        if response.status_code >= 400:
            error_msg = response.text.strip() or f"HTTP {response.status_code}"
            logger.error(
                "Webhook HTTP %s: %s (URL: %s)", 
                response.status_code, 
                error_msg,
                formatter.WEBHOOK_URL
            )
            logger.info("Falling back to approval request due to webhook error")
            if forwarded_msg:
                await send_approval_request(event.client, formatted_text, forwarded_msg.id)
            return

        logger.info(
            "✅ Auto-forwarded message id=%s to webhook status=%s",
            message.id,
            response.status_code,
        )

        # Also forward refined text to any configured extra topics
        try:
            formatter.forward_to_additional_topics(formatted_text)
        except Exception as exc:
            logger.exception("Extra topic forwarding from user_forwarder failed: %s", exc)
    else:
        # Step 3b: Messages needing approval → DON'T forward to subtopic, ONLY send approval request
        logger.info("Requesting approval for message id=%s (doesn't match auto-forward criteria, NOT forwarding to subtopic)", message.id)
        # Use a dummy message ID for the approval request (since we're not forwarding)
        dummy_msg_id = message.id  # Use channel message ID as reference
        await send_approval_request(event.client, formatted_text, dummy_msg_id)


async def main() -> None:
    api_id = int(API_ID)
    api_hash = API_HASH

    async with TelegramClient(SESSION_NAME, api_id, api_hash) as client:
        # Verify we can access the channel
        try:
            channel_entity = await client.get_entity(SOURCE_CHANNEL)
            logger.info(
                "Channel entity resolved: id=%s, title=%s",
                channel_entity.id,
                getattr(channel_entity, "title", "N/A"),
            )

            try:
                logger.info("Attempting to join channel %s...", SOURCE_CHANNEL)
                await client(JoinChannelRequest(channel_entity))
                logger.info("Join channel request completed (or already a member).")
            except Exception as join_exc:
                logger.warning(
                    "Join channel request failed (possibly already joined): %s",
                    join_exc,
                )
        except Exception as exc:
            logger.error(
                "Failed to resolve channel %s: %s. Make sure you're subscribed to it.",
                SOURCE_CHANNEL,
                exc,
            )
            raise

        logger.info(
            "Listening as user session '%s' for channel=%s (id=%s), forwarding to chat=%s thread=%s",
            SESSION_NAME,
            SOURCE_CHANNEL,
            channel_entity.id,
            FORWARD_TO_CHAT_ID,
            FORWARD_TO_THREAD_ID,
        )

        # Listen for incoming posts in the channel
        @client.on(events.NewMessage(chats=channel_entity, incoming=True))
        async def handler(event):
            logger.info(
                "Received INCOMING message from channel: id=%s, text=%r, is_channel=%s, chat_id=%s",
                event.message.id,
                (event.message.message or "")[:100],
                event.is_channel,
                event.chat_id,
            )
            await process_channel_message(event)

        # Some channel posts appear as outgoing for the publishing account
        @client.on(events.NewMessage(chats=channel_entity, outgoing=True))
        async def handler_out(event):
            logger.info(
                "Received OUTGOING message from channel: id=%s, text=%r, is_channel=%s, chat_id=%s",
                event.message.id,
                (event.message.message or "")[:100],
                event.is_channel,
                event.chat_id,
            )
            await process_channel_message(event)

        # Catch-all debug to ensure nothing slips through
        @client.on(events.NewMessage())
        async def debug_handler(event):
            if event.chat_id == channel_entity.id:
                logger.info(
                    "DEBUG catch-all: id=%s, out=%s, in=%s, text=%r",
                    event.message.id,
                    event.out,
                    event.is_channel,
                    (event.message.message or "")[:100],
                )

        logger.info("Event handlers registered. Waiting for messages...")
        await client.run_until_disconnected()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("User forwarder stopped manually.")

