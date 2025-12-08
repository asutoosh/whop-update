"""
Forward filtered Telegram messages to a webhook with manual approval.

Requirements:
    pip install python-telegram-bot>=21.0 requests python-dotenv

Security hardening:
    - Set WEBHOOK_SHARED_SECRET to enable HMAC signatures on outbound payloads.
    - Ensure WEBHOOK_URL points to an HTTPS endpoint unless ALLOW_INSECURE_WEBHOOK=true.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

try:
    from telegram.ext import AIORateLimiter
except ImportError:  # pragma: no cover - optional dependency
    AIORateLimiter = None  # type: ignore[assignment]

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://example.com/your-webhook")
# Optional shared secret for signing outbound webhook payloads (HMAC-SHA256)
WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET")
WEBHOOK_SIGNATURE_HEADER = os.getenv(
    "WEBHOOK_SIGNATURE_HEADER", "X-Webhook-Signature"
).strip()
# Allow opting into HTTP (discouraged). Default requires HTTPS.
ALLOW_INSECURE_WEBHOOK = (
    os.getenv("ALLOW_INSECURE_WEBHOOK", "false").strip().lower()
    in {"1", "true", "yes"}
)

# How to deliver data to webhook: "json" (default), "form", or "text"
WEBHOOK_SEND_MODE = os.getenv("WEBHOOK_SEND_MODE", "json").strip().lower()
# Key name for formatted text when using json/form modes
WEBHOOK_PAYLOAD_KEY = os.getenv("WEBHOOK_PAYLOAD_KEY", "text").strip()
# Whether to include meta information (if available) in payload (json/form modes only)
WEBHOOK_INCLUDE_META = os.getenv("WEBHOOK_INCLUDE_META", "false").strip().lower() in {
    "1",
    "true",
    "yes",
}
# Whether to require Telegram's forwarded flag on messages before processing
REQUIRE_FORWARDED = (
    os.getenv("REQUIRE_FORWARDED", "true").strip().lower() in {"1", "true", "yes"}
)
# Whether to include the "script" line in formatted trade output.
# Default is now TRUE so that signal names (symbols) are preserved in all
# forwarded messages. You can disable it by setting INCLUDE_SCRIPT_LINE=false.
INCLUDE_SCRIPT_LINE = (
    os.getenv("INCLUDE_SCRIPT_LINE", "true").strip().lower() in {"1", "true", "yes"}
)

# Limit processing to specific chats (comma-separated chat IDs). Leave empty for all.
ALLOWED_CHAT_IDS: set[int] = {
    int(cid.strip())
    for cid in os.getenv("ALLOWED_CHAT_IDS", "").split(",")
    if cid.strip().lstrip("-").isdigit()
}

# Limit processing to specific topic threads inside supergroups.
# Format: chat_id:thread_id, multiple pairs separated by commas.
raw_topics = os.getenv("ALLOWED_TOPICS", "")
_topics_raw = [entry.strip() for entry in raw_topics.replace(";", ",").split(",") if entry.strip()]
ALLOWED_TOPICS: set[tuple[int, int]] = set()
if raw_topics.strip():
    for entry in _topics_raw:
        parts = entry.replace("|", ":").split(":")
        if len(parts) != 2:
            logging.getLogger("forwarder_bot").warning(
                "Invalid ALLOWED_TOPICS entry (expected chat_id:thread_id): %s", entry
            )
            continue
        chat_part, thread_part = parts
        if not chat_part.strip() or not thread_part.strip():
            logging.getLogger("forwarder_bot").warning(
                "Invalid ALLOWED_TOPICS entry (missing chat/thread): %s", entry
            )
            continue
        try:
            chat_id_val = int(chat_part.strip())
            thread_id_val = int(thread_part.strip())
        except ValueError:
            logging.getLogger("forwarder_bot").warning(
                "Invalid ALLOWED_TOPICS entry (non-numeric): %s", entry
            )
            continue
        ALLOWED_TOPICS.add((chat_id_val, thread_id_val))

# Telegram user IDs that are allowed to approve forwards.
# Add your user ID here (and the IDs of any trusted moderators).
APPROVER_IDS: List[int] = [
    int(uid.strip())
    for uid in os.getenv("APPROVER_IDS", "").split(",")
    if uid.strip().isdigit()
]

# phrases/words to remove from forwarded message (case-insensitive)
BANNED_PHRASES: List[str] = [
    r"wazir\s+algo",
    r"wazir\s+forex\s+algo",
    r"wazir\s+forex",
    r"\bany\s+inquiries\s+dm\s+@\w+",
    r"\bdm\s+@\w+",
    r"\bcontact\s+@\w+",
    r"\bfor\s+inquiries\s+dm\s+@\w+",
    r"\bany\s+inquiries\b",
]

PRICE_RE = re.compile(r"\b\d{1,6}(?:[.,]\d{1,6})?\b")
SYMBOL_RE = re.compile(r"\b([A-Z]{2,6}\d{0,4}(?:\/[A-Z]{2,6}\d{0,4})?)\b")
STATUS_RE = re.compile(
    r"(TAKE\s*PROFIT\s*\d+\s+FROM\s+[A-Z ]+\s+SIGNAL.*|HIT\s+(?:TP|SL).*)",
    flags=re.IGNORECASE | re.DOTALL,
)

STATUS_ONLY_PREFIXES = (
    "POSITION STATUS",
    "TAKE PROFIT",
    "HIT TP",
    "HIT SL",
    "TP ",
    "SL ",
)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(levelname)s:%(name)s:%(message)s",
)
logger = logging.getLogger("forwarder_bot")

# Optional extra forwarding destinations (two additional group subtopics)
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

def _parse_chat_id(raw: Optional[str]) -> Optional[int]:
    """Parse and convert chat ID to Bot API format."""
    if not raw or not raw.strip().lstrip("-").isdigit():
        return None
    raw_id = int(raw.strip())
    # Convert to Bot API format if it's a positive ID (Telethon format)
    if raw_id > 0:
        return convert_to_bot_api_id(raw_id)
    return raw_id  # Already in Bot API format

EXTRA_FORWARD_1_CHAT_ID_RAW = os.getenv("EXTRA_FORWARD_1_CHAT_ID")
EXTRA_FORWARD_1_THREAD_ID_RAW = os.getenv("EXTRA_FORWARD_1_THREAD_ID")
EXTRA_FORWARD_2_CHAT_ID_RAW = os.getenv("EXTRA_FORWARD_2_CHAT_ID")
EXTRA_FORWARD_2_THREAD_ID_RAW = os.getenv("EXTRA_FORWARD_2_THREAD_ID")

EXTRA_FORWARD_1_CHAT_ID: Optional[int] = _parse_chat_id(EXTRA_FORWARD_1_CHAT_ID_RAW)
EXTRA_FORWARD_1_THREAD_ID: Optional[int] = (
    int(EXTRA_FORWARD_1_THREAD_ID_RAW)
    if EXTRA_FORWARD_1_THREAD_ID_RAW and EXTRA_FORWARD_1_THREAD_ID_RAW.strip().isdigit()
    else None
)
EXTRA_FORWARD_2_CHAT_ID: Optional[int] = _parse_chat_id(EXTRA_FORWARD_2_CHAT_ID_RAW)
EXTRA_FORWARD_2_THREAD_ID: Optional[int] = (
    int(EXTRA_FORWARD_2_THREAD_ID_RAW)
    if EXTRA_FORWARD_2_THREAD_ID_RAW and EXTRA_FORWARD_2_THREAD_ID_RAW.strip().isdigit()
    else None
)


def remove_banned(text: str) -> str:
    cleaned = text
    for pattern in BANNED_PHRASES:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\n", "\n", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def is_status_only_message(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    upper = stripped.upper()
    return any(upper.startswith(prefix) for prefix in STATUS_ONLY_PREFIXES)


def _norm_price(value: str) -> str:
    return value.replace(",", ".")


def append_field(
    lines: List[str],
    label: str,
    value: Optional[str],
    *,
    fallback: str = "N/A",
    include_if_missing: bool = False,
    multiline: bool = False,
) -> None:
    raw_value = (value or "").strip()
    if not raw_value:
        if not include_if_missing:
            return
        raw_value = fallback

    if multiline:
        lines.append(f"{label} :")
        lines.append(raw_value)
    else:
        lines.append(f"{label.ljust(15)}: {raw_value}")


@dataclass
class TradeInfo:
    script: Optional[str] = None
    position: Optional[str] = None
    enter: Optional[str] = None
    tps: List[str] | None = None
    stoploss: Optional[str] = None
    position_status: Optional[str] = None
    raw_status_block: Optional[str] = None


def parse_trade(text: str) -> TradeInfo:
    upper_text = text.upper()
    trade = TradeInfo(tps=[])

    # First, try to extract symbol from "script : SYMBOL" pattern
    script_line_match = re.search(
        r"SCRIPT\s*[:\-]?\s*([A-Z]{2,6}\d{0,4}(?:\/[A-Z]{2,6}\d{0,4})?)", 
        upper_text, 
        re.IGNORECASE
    )
    if script_line_match:
        trade.script = script_line_match.group(1).replace("/", "")
    else:
        # Fall back to general symbol search, but exclude common words
        excluded_words = {
            "SCRIPT", "POSITION", "ENTER", "PRICE", "TAKE", "PROFIT", 
            "STOP", "LOSS", "STOPLOSS", "SL", "TP", "BUY", "SELL", 
            "LONG", "SHORT", "STATUS", "FROM", "SIGNAL", "AT", "IN"
        }
        # Find all potential symbols
        for symbol_match in SYMBOL_RE.finditer(upper_text):
            candidate = symbol_match.group(1).replace("/", "")
            # Skip if it's a common word
            if candidate not in excluded_words and len(candidate) >= 3:
                trade.script = candidate
                break

    pos_match = re.search(r"\b(BUY|SELL|LONG|SHORT)\b", upper_text)
    if pos_match:
        pos = pos_match.group(1)
        trade.position = "BUY" if pos in ("BUY", "LONG") else "SELL"

    prices = [_norm_price(p) for p in PRICE_RE.findall(text)]

    enter_match = re.search(r"ENTER\s*PRICE\s*[:\-]?\s*([0-9.,]+)", text, re.IGNORECASE)
    if enter_match:
        trade.enter = _norm_price(enter_match.group(1))

    for tp_match in re.finditer(
        r"(TAKE\s*PROFIT\s*\d*|TP\s*\d*)\s*[:\-]?\s*([0-9.,]+)", text, re.IGNORECASE
    ):
        trade.tps.append(_norm_price(tp_match.group(2)))

    sl_match = re.search(
        r"(STOP\s*LOSS|STOPLOSS|SL)\s*[:\-]?\s*([0-9.,]+)", text, re.IGNORECASE
    )
    if sl_match:
        trade.stoploss = _norm_price(sl_match.group(2))

    if not trade.enter and prices:
        trade.enter = prices[0]

    if not trade.stoploss and len(prices) >= 2:
        trade.stoploss = prices[-1]

    if not trade.tps:
        dedup: List[str] = []
        for price in prices:
            if price not in dedup:
                dedup.append(price)
        for field in (trade.enter, trade.stoploss):
            if field and field in dedup:
                dedup.remove(field)
        trade.tps = dedup[:4]

    status_match = STATUS_RE.search(text)
    if status_match:
        trade.raw_status_block = status_match.group(1).strip()

    explicit_status = re.search(
        r"\b(HIT\s*TP\d*|HIT\s*SL|POSITION\s*STATUS|CLOSED|EXPIRED)\b",
        text,
        re.IGNORECASE,
    )
    if explicit_status:
        trade.position_status = explicit_status.group(1).upper()

    return trade


def build_formatted(trade: TradeInfo, cleaned_text: str) -> str:
    lines: List[str] = []

    has_trade_core = any([trade.script, trade.position, trade.enter, trade.tps])
    status_only = not has_trade_core and (trade.position_status or trade.raw_status_block)

    if has_trade_core:
        if INCLUDE_SCRIPT_LINE:
            append_field(lines, "script", trade.script, include_if_missing=True)
        position_value = trade.position
        if position_value:
            normalized = position_value.upper()
            if normalized == "SELL":
                position_value = "SELL ⬇️"
            elif normalized == "BUY":
                position_value = "BUY ⬆️"
        append_field(lines, "Position", position_value)
        append_field(lines, "Enter Price", trade.enter)
        for idx, tp in enumerate(trade.tps[:4], start=1):
            append_field(lines, f"Take Profit {idx}", tp)
        append_field(lines, "Stoploss", trade.stoploss)

    if trade.position_status or trade.raw_status_block or status_only:
        if lines:
            lines.append("")
        status_lines: List[str] = []
        if trade.position_status:
            status_lines.append(trade.position_status.title())
        if trade.raw_status_block:
            status_lines.append(trade.raw_status_block)
        append_field(
            lines,
            "Position Status",
            "\n".join(status_lines) if status_lines else None,
            include_if_missing=True,
            multiline=True,
        )

    if not lines:
        snippet = cleaned_text.strip()
        if len(snippet) > 900:
            snippet = snippet[:900] + "..."
        lines.append(snippet)

    return "\n".join(lines).strip()


def build_meta(update: Update) -> Optional[str]:
    message = update.effective_message
    if not message:
        return None

    parts: List[str] = []
    if message.forward_from_chat:
        name = message.forward_from_chat.title or message.forward_from_chat.username
        if name:
            parts.append(f"forwarded_from: {name}")
    if message.forward_sender_name:
        parts.append(f"forwarded_sender_name: {message.forward_sender_name}")
    if message.forward_from:
        parts.append(f"forwarded_user: {message.forward_from.id}")
    return " | ".join(parts) if parts else None


def build_webhook_payload(
    formatted: str, meta: Optional[str]
) -> Dict[str, Optional[str]] | str:
    if WEBHOOK_SEND_MODE == "text":
        return formatted

    payload: Dict[str, Optional[str]] = {WEBHOOK_PAYLOAD_KEY: formatted}
    # Many webhooks (e.g., Discord) expect the field to be called "content"
    if WEBHOOK_PAYLOAD_KEY != "content":
        payload.setdefault("content", formatted)
    if WEBHOOK_INCLUDE_META and meta:
        payload["meta"] = meta
    return payload


def require_approver(user_id: Optional[int]) -> bool:
    if not APPROVER_IDS:
        return True
    return user_id in APPROVER_IDS


def _short_preview(text: str, limit: int = 160) -> str:
    preview = text.replace("\n", " ")
    if len(preview) > limit:
        preview = preview[: limit - 3] + "..."
    return preview


def _build_prepared_request(
    payload: Dict[str, Optional[str]] | str, formatted_text: str
) -> requests.PreparedRequest:
    headers: Dict[str, str] = {"User-Agent": "tg-forwarder-bot/1.0"}

    if WEBHOOK_SEND_MODE == "text":
        headers["Content-Type"] = "text/plain; charset=utf-8"
        request = requests.Request(
            "POST", WEBHOOK_URL, headers=headers, data=formatted_text.encode("utf-8")
        )
    elif WEBHOOK_SEND_MODE == "form":
        assert isinstance(payload, dict)
        request = requests.Request(
            "POST",
            WEBHOOK_URL,
            headers=headers,
            data=payload,
        )
    else:
        assert isinstance(payload, dict)
        headers["Content-Type"] = "application/json; charset=utf-8"
        request = requests.Request(
            "POST",
            WEBHOOK_URL,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            ),
        )

    return request.prepare()


def _attach_signature(prepared: requests.PreparedRequest) -> None:
    if not WEBHOOK_SHARED_SECRET:
        return
    body = prepared.body or b""
    if isinstance(body, str):
        body = body.encode("utf-8")
    signature = hmac.new(
        WEBHOOK_SHARED_SECRET.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()
    prepared.headers[WEBHOOK_SIGNATURE_HEADER] = signature


def post_to_webhook(payload: Dict[str, Optional[str]] | str, formatted_text: str):
    logger.info("Posting to webhook (mode=%s)", WEBHOOK_SEND_MODE)
    logger.debug("Webhook target: %s", WEBHOOK_URL)
    logger.debug("Formatted preview: %s", _short_preview(formatted_text))
    if isinstance(payload, dict):
        logger.debug("Payload keys: %s", list(payload.keys()))

    prepared = _build_prepared_request(payload, formatted_text)
    _attach_signature(prepared)

    with requests.Session() as session:
        response = session.send(prepared, timeout=10)

    logger.info("Webhook response status=%s", response.status_code)
    logger.debug("Webhook response body (truncated): %s", response.text[:200])
    return response


def forward_to_additional_topics(formatted_text: str) -> None:
    """
    Optionally forward the refined / formatted text to up to two extra
    group subtopics, using the same bot token. Controlled via:

      EXTRA_FORWARD_1_CHAT_ID, EXTRA_FORWARD_1_THREAD_ID
      EXTRA_FORWARD_2_CHAT_ID, EXTRA_FORWARD_2_THREAD_ID
    """
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        logger.warning(
            "Skipping extra topic forwarding because BOT_TOKEN is not configured."
        )
        return

    targets: List[tuple[int, Optional[int]]] = []
    if EXTRA_FORWARD_1_CHAT_ID is not None:
        targets.append((EXTRA_FORWARD_1_CHAT_ID, EXTRA_FORWARD_1_THREAD_ID))
    if EXTRA_FORWARD_2_CHAT_ID is not None:
        targets.append((EXTRA_FORWARD_2_CHAT_ID, EXTRA_FORWARD_2_THREAD_ID))

    if not targets:
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id, thread_id in targets:
        params: Dict[str, object] = {
            "chat_id": chat_id,
            "text": formatted_text,
        }
        if thread_id is not None:
            params["message_thread_id"] = thread_id

        try:
            logger.info(
                "Forwarding refined text to extra destination chat_id=%s thread_id=%s",
                chat_id,
                thread_id,
            )
            resp = requests.post(url, json=params, timeout=10)
            if resp.status_code >= 400:
                logger.error(
                    "Extra topic forward failed for chat_id=%s thread_id=%s: HTTP %s %s",
                    chat_id,
                    thread_id,
                    resp.status_code,
                    resp.text[:200],
                )
            else:
                logger.info(
                    "Extra topic forward succeeded for chat_id=%s thread_id=%s status=%s",
                    chat_id,
                    thread_id,
                    resp.status_code,
                )
        except Exception as exc:
            logger.exception(
                "Error while forwarding to extra destination chat_id=%s thread_id=%s: %s",
                chat_id,
                thread_id,
                exc,
            )


@dataclass
class PendingForward:
    payload: Dict[str, Optional[str]] | str
    formatted_text: str
    approval_message_id: int
    chat_id: int
    original_message_id: int
    original_thread_id: Optional[int]


def get_pending_store(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, PendingForward]:
    bot_data = context.application.bot_data
    if "pending_forwards" not in bot_data:
        bot_data["pending_forwards"] = {}
    return bot_data["pending_forwards"]  # type: ignore[return-value]


async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if not message:
        return

    chat = message.chat or message.sender_chat
    chat_id = chat.id if chat else message.chat_id
    thread_id = getattr(message, "message_thread_id", None)

    logger.info(
        "Incoming message chat_id=%s thread_id=%s forward=%s text_present=%s raw=%r",
        chat_id,
        thread_id,
        bool(
            message.forward_from
            or message.forward_from_chat
            or message.forward_sender_name
            or message.forward_date
        ),
        bool(message.text or message.caption),
        (message.text or message.caption or "")[:200],
    )

    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        logger.info("Skipping chat %s not in ALLOWED_CHAT_IDS", chat_id)
        return

    if ALLOWED_TOPICS:
        if thread_id is None:
            logger.info(
                "Skipping chat %s message without topic (ALLOWED_TOPICS configured)",
                chat_id,
            )
            return
        if (chat_id, thread_id) not in ALLOWED_TOPICS:
            logger.info(
                "Skipping message from chat %s thread %s not in ALLOWED_TOPICS",
                chat_id,
                thread_id,
            )
            return

    if REQUIRE_FORWARDED and not (
        message.forward_from
        or message.forward_from_chat
        or message.forward_sender_name
        or message.forward_date
    ):
        return

    original_text = message.text or message.caption
    if not original_text:
        return

    cleaned = remove_banned(original_text)
    if not cleaned:
        logger.info("Message cleaned to empty content; skipping.")
        return

    status_only_override = False
    if is_status_only_message(cleaned):
        status_only_override = True

    trade = parse_trade(cleaned)
    if status_only_override:
        formatted = cleaned.strip()
    else:
        formatted = build_formatted(trade, cleaned)
    meta = build_meta(update)

    payload = build_webhook_payload(formatted, meta)

    pending_store = get_pending_store(context)
    key = f"{chat_id}:{message.message_id}"

    lower_cleaned = cleaned.lower()
    auto_forward = status_only_override or (
        not status_only_override
        and (
            (trade.position and trade.enter)
            or ("position" in lower_cleaned and "enter price" in lower_cleaned)
        )
    )

    if auto_forward:
        try:
            response = post_to_webhook(payload, formatted)
        except Exception as exc:
            logger.exception("Webhook post failed: %s", exc)
            await message.reply_text(
                "⚠️ Auto-forward webhook failed. Please check logs.",
                allow_sending_without_reply=True,
            )
            return

        if response.status_code >= 400:
            logger.error(
                "Webhook HTTP %s: %s", response.status_code, response.text.strip()
            )
            await message.reply_text(
                "⚠️ Auto-forward webhook rejected the payload. Check logs.",
                allow_sending_without_reply=True,
            )
            return

        logger.info("Auto-forwarded to webhook status=%s", response.status_code)
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Allow Forward ✅", callback_data=f"allow|{key}"),
                InlineKeyboardButton("Deny 🚫", callback_data=f"deny|{key}"),
            ]
        ]
    )

    escaped = html.escape(formatted)
    preview = f"Ready to forward this message?\n\n<pre>{escaped}</pre>"
    preview = preview[:4000]

    approval_message = await message.reply_text(
        preview,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True,
        allow_sending_without_reply=True,
    )

    pending_store[key] = PendingForward(
        payload=payload,
        formatted_text=formatted,
        approval_message_id=approval_message.message_id,
        chat_id=message.chat_id,
        original_thread_id=thread_id,
        original_message_id=message.message_id,
    )


async def handle_approval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    logger.info(
        "Callback query received: from_user=%s, chat=%s, data=%s",
        query.from_user.id if query.from_user else None,
        query.message.chat.id if query.message else None,
        query.data,
    )

    user_id = query.from_user.id if query.from_user else None
    if not require_approver(user_id):
        logger.warning("User %s is not in APPROVER_IDS list", user_id)
        await query.answer("You are not allowed to approve forwards.", show_alert=True)
        return

    if not query.data:
        logger.warning("Callback query has no data")
        await query.answer()
        return

    action, _, key = query.data.partition("|")
    logger.info("Processing callback: action=%s, key=%s", action, key)
    
    pending_store = get_pending_store(context)
    pending = pending_store.get(key)
    
    logger.info("Pending store lookup: key=%s, found=%s", key, pending is not None)

    # If pending not found, try to extract formatted text from the approval message itself
    if not pending:
        logger.info("Pending forward not found for key=%s, trying to extract from message", key)
        approval_msg = query.message
        if approval_msg and approval_msg.text:
            logger.info("Extracting text from approval message: %s", approval_msg.text[:200])
            # Extract the formatted text from the HTML pre tag
            import re
            # Try to get HTML text - telegram library provides entities
            msg_text = approval_msg.text
            # Look for content between <pre> tags or extract from entities
            pre_match = re.search(r"<pre>(.*?)</pre>", msg_text, re.DOTALL)
            if not pre_match:
                # Try without HTML tags - might be plain text
                # Look for the formatted content after "Ready to forward this message?"
                lines = msg_text.split("\n")
                if len(lines) > 2:
                    # Skip first two lines ("Ready to forward..." and empty line)
                    formatted_text = "\n".join(lines[2:]).strip()
                else:
                    formatted_text = msg_text
            else:
                formatted_text = html.unescape(pre_match.group(1))
            
            if formatted_text:
                # Rebuild payload
                payload = build_webhook_payload(formatted_text, meta=None)
                logger.info("Extracted formatted text from approval message, forwarding to webhook")
                
                if action == "allow":
                    try:
                        response = post_to_webhook(payload, formatted_text)
                        if response.status_code >= 400:
                            error_msg = response.text.strip() or f"HTTP {response.status_code}"
                            logger.error(
                                "Webhook HTTP %s: %s (URL: %s)", 
                                response.status_code, 
                                error_msg,
                                WEBHOOK_URL
                            )
                            await query.answer("Webhook rejected payload.", show_alert=True)
                            await query.edit_message_text(
                                f"⚠️ Webhook error {response.status_code}: {error_msg[:200]}"
                            )
                            return
                        
                        logger.info("Webhook accepted message status=%s", response.status_code)
                        # Also forward refined text to any configured extra topics
                        forward_to_additional_topics(formatted_text)
                        await query.answer("Forwarded to webhook.")
                        escaped = html.escape(formatted_text)
                        confirmation = f"✅ Forwarded.\n\n<pre>{escaped}</pre>"
                        await query.edit_message_text(
                            confirmation[:4000],
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception as exc:
                        logger.exception("Webhook post failed: %s", exc)
                        await query.answer("Webhook failed. Check logs.", show_alert=True)
                        return
                else:
                    await query.answer("Forward denied.")
                    await query.edit_message_text("🚫 Forward denied.")
                return
        
        await query.answer("No pending item or already processed.", show_alert=False)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    if action == "allow":
        try:
            response = post_to_webhook(pending.payload, pending.formatted_text)
        except Exception as exc:
            logger.exception("Webhook post failed: %s", exc)
            await query.answer("Webhook failed. Check logs.", show_alert=True)
            return

        if response.status_code >= 400:
            error_msg = response.text.strip() or f"HTTP {response.status_code}"
            logger.error(
                "Webhook HTTP %s: %s (URL: %s)", 
                response.status_code, 
                error_msg,
                WEBHOOK_URL
            )
            await query.answer("Webhook rejected payload.", show_alert=True)
            await query.edit_message_text(
                f"⚠️ Webhook error {response.status_code}: {error_msg[:200]}"
            )
            return

        logger.info("Webhook accepted message status=%s", response.status_code)
        # Also forward refined text to any configured extra topics
        forward_to_additional_topics(pending.formatted_text)
        await query.answer("Forwarded to webhook.")
        escaped = html.escape(pending.formatted_text)
        confirmation = f"✅ Forwarded.\n\n<pre>{escaped}</pre>"
        await query.edit_message_text(
            confirmation[:4000],
            parse_mode=ParseMode.HTML,
        )
    else:
        await query.answer("Forward denied.")
        await query.edit_message_text("🚫 Forward denied.")

    pending_store.pop(key, None)


def build_application() -> Application:
    if BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise RuntimeError("Set BOT_TOKEN env var or edit BOT_TOKEN constant.")
    if WEBHOOK_URL == "https://example.com/your-webhook":
        logger.warning("WEBHOOK_URL is still default placeholder.")
    if not ALLOW_INSECURE_WEBHOOK and not WEBHOOK_URL.lower().startswith("https://"):
        raise RuntimeError(
            "WEBHOOK_URL must use HTTPS (set ALLOW_INSECURE_WEBHOOK=true to override for testing)."
        )

    builder = ApplicationBuilder().token(BOT_TOKEN)
    if AIORateLimiter:
        try:
            builder = builder.rate_limiter(AIORateLimiter())
        except RuntimeError as e:
            logger.warning(
                "AIORateLimiter initialization failed: %s. Continuing without rate limiter.",
                e,
            )
    else:
        logger.warning(
            "AIORateLimiter not available. Install python-telegram-bot[rate-limiter] "
            "for better flood protection."
        )

    app = builder.build()

    app.add_handler(MessageHandler(filters.ALL, handle_forward), group=0)
    app.add_handler(CallbackQueryHandler(handle_approval))

    return app


def main() -> None:
    application = build_application()
    logger.info("Bot started. Waiting for forwarded messages...")
    application.run_polling(
        close_loop=False,
        allowed_updates=["message", "edited_message", "callback_query"],
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped manually.")

