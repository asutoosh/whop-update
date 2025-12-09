# user_forwarder.py - WITH APPROVAL SYSTEM
"""
Userbot watcher for signals with approval system:
- Watches SOURCE_CHANNEL for new messages.
- For every text message:
    1) Sends raw text to Freya ingest API
    2) If Freya recognizes it (status=success) → forwards immediately
    3) If Freya doesn't recognize it → sends approval request to APPROVAL_CHAT_ID
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
import hashlib

import requests
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import ChannelInvalidError, ChannelPrivateError
from telethon.tl.functions.channels import JoinChannelRequest

# ---------------------------------------------------------------------------
# Env & logging
# ---------------------------------------------------------------------------

load_dotenv()

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
SESSION_NAME = os.getenv("USERBOT_SESSION", "user_forwarder").strip()

SOURCE_CHANNEL = os.getenv("SOURCE_CHANNEL", "").strip()

FORWARD_TO_CHAT_ID = os.getenv("FORWARD_TO_CHAT_ID", "").strip()
FORWARD_TO_THREAD_ID = os.getenv("FORWARD_TO_THREAD_ID", "").strip()

EXTRA_FORWARD_1_CHAT_ID = os.getenv("EXTRA_FORWARD_1_CHAT_ID", "").strip()
EXTRA_FORWARD_1_THREAD_ID = os.getenv("EXTRA_FORWARD_1_THREAD_ID", "").strip()
EXTRA_FORWARD_2_CHAT_ID = os.getenv("EXTRA_FORWARD_2_CHAT_ID", "").strip()
EXTRA_FORWARD_2_THREAD_ID = os.getenv("EXTRA_FORWARD_2_THREAD_ID", "").strip()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

APPROVAL_CHAT_ID = os.getenv("APPROVAL_CHAT_ID", "").strip()

WEBHOOK_URL = os.getenv("WHOP_WEBHOOK_URL", "").strip() or os.getenv(
    "WEBHOOK_URL", ""
).strip()
WEBHOOK_SEND_MODE = os.getenv("WEBHOOK_SEND_MODE", "json").strip().lower()
WEBHOOK_PAYLOAD_KEY = os.getenv("WEBHOOK_PAYLOAD_KEY", "content").strip()
WEBHOOK_INCLUDE_META = os.getenv("WEBHOOK_INCLUDE_META", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)

WEBHOOK_SHARED_SECRET = os.getenv("WEBHOOK_SHARED_SECRET", "").strip()
WEBHOOK_SIGNATURE_HEADER = os.getenv(
    "WEBHOOK_SIGNATURE_HEADER", "X-Webhook-Signature"
).strip()
ALLOW_INSECURE_WEBHOOK = os.getenv("ALLOW_INSECURE_WEBHOOK", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)

ALLOWED_CHAT_IDS_RAW = os.getenv("ALLOWED_CHAT_IDS", "").strip()
ALLOWED_TOPICS_RAW = os.getenv("ALLOWED_TOPICS", "").strip()
REQUIRE_FORWARDED = os.getenv("REQUIRE_FORWARDED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)

INCLUDE_SCRIPT_LINE = os.getenv("INCLUDE_SCRIPT_LINE", "true").strip().lower() in (
    "1",
    "true",
    "yes",
)

LOG_LEVEL = os.getenv("USERBOT_LOG_LEVEL", "INFO").upper()

WEBSITE_API_URL = os.getenv("WEBSITE_API_URL", "").strip()
INGEST_API_KEY = os.getenv("INGEST_API_KEY", "").strip()

FORWARD_STATE_FILE = "forward_state.json"
PENDING_APPROVALS_FILE = "pending_approvals.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger("user_forwarder")

if not API_ID or not API_HASH:
    raise SystemExit("❌ API_ID and API_HASH are required in .env")

if not SOURCE_CHANNEL:
    raise SystemExit("❌ SOURCE_CHANNEL is required in .env")

if not BOT_TOKEN:
    logger.warning("BOT_TOKEN is not set – forwarding to Telegram groups will not work.")

# ---------------------------------------------------------------------------
# Helpers: parse IDs, allowed lists
# ---------------------------------------------------------------------------

def _parse_int_or_none(value: str) -> Optional[int]:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None

def _parse_chat_id_list(raw: str) -> List[int]:
    if not raw:
        return []
    out: List[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        v = _parse_int_or_none(part)
        if v is not None:
            out.append(v)
    return out

def _parse_topics(raw: str) -> List[Tuple[int, int]]:
    if not raw:
        return []
    out: List[Tuple[int, int]] = []
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if ":" not in pair:
            continue
        chat_str, thread_str = pair.split(":", 1)
        chat_id = _parse_int_or_none(chat_str)
        thread_id = _parse_int_or_none(thread_str)
        if chat_id is not None and thread_id is not None:
            out.append((chat_id, thread_id))
    return out

ALLOWED_CHAT_IDS = _parse_chat_id_list(ALLOWED_CHAT_IDS_RAW)
ALLOWED_TOPICS = _parse_topics(ALLOWED_TOPICS_RAW)

MAIN_CHAT_ID = _parse_int_or_none(FORWARD_TO_CHAT_ID)
MAIN_THREAD_ID = _parse_int_or_none(FORWARD_TO_THREAD_ID)

EXTRA1_CHAT_ID = _parse_int_or_none(EXTRA_FORWARD_1_CHAT_ID)
EXTRA1_THREAD_ID = _parse_int_or_none(EXTRA_FORWARD_1_THREAD_ID)
EXTRA2_CHAT_ID = _parse_int_or_none(EXTRA_FORWARD_2_CHAT_ID)
EXTRA2_THREAD_ID = _parse_int_or_none(EXTRA_FORWARD_2_THREAD_ID)

APPROVAL_CHAT_ID_INT = _parse_int_or_none(APPROVAL_CHAT_ID)

# ---------------------------------------------------------------------------
# Pending approvals storage
# ---------------------------------------------------------------------------

def load_pending_approvals() -> Dict[str, Dict[str, Any]]:
    try:
        with open(PENDING_APPROVALS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception as exc:
        logger.warning("Could not read %s: %s", PENDING_APPROVALS_FILE, exc)
        return {}

def save_pending_approvals(data: Dict[str, Dict[str, Any]]) -> None:
    try:
        with open(PENDING_APPROVALS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as exc:
        logger.error("Could not write %s: %s", PENDING_APPROVALS_FILE, exc)

def add_pending_approval(text: str, signal_obj: Dict[str, Any]) -> str:
    """Add a message to pending approvals, return approval_id"""
    approval_id = hashlib.md5(text.encode()).hexdigest()[:12]
    pending = load_pending_approvals()
    pending[approval_id] = {
        "text": text,
        "signal_obj": signal_obj,
        "timestamp": asyncio.get_event_loop().time()
    }
    save_pending_approvals(pending)
    return approval_id

def get_pending_approval(approval_id: str) -> Optional[Dict[str, Any]]:
    pending = load_pending_approvals()
    return pending.get(approval_id)

def remove_pending_approval(approval_id: str) -> None:
    pending = load_pending_approvals()
    if approval_id in pending:
        del pending[approval_id]
        save_pending_approvals(pending)

# ---------------------------------------------------------------------------
# Shared forwarding state
# ---------------------------------------------------------------------------

def is_forwarding_enabled() -> bool:
    try:
        with open(FORWARD_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return bool(data.get("enabled", True))
    except FileNotFoundError:
        return True
    except Exception as exc:
        logger.warning("Could not read %s: %s", FORWARD_STATE_FILE, exc)
        return True

# ---------------------------------------------------------------------------
# Freya ingest API
# ---------------------------------------------------------------------------

def call_freya_ingest(message_text: str) -> Dict[str, Any]:
    if not WEBSITE_API_URL or not INGEST_API_KEY:
        logger.debug("Freya ingest not configured, skipping.")
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

        status_field = data.get("status", "unknown")
        logger.info(
            "Freya ingest response: http=%s, status=%s",
            resp.status_code,
            status_field,
        )
        return {
            "success": resp.status_code == 200,
            "status": status_field,
            "data": data,
        }
    except Exception as exc:
        logger.exception("❌ Freya ingest request failed: %s", exc)
        return {"success": False, "status": "error", "data": None}

def build_signal_text(signal: Dict[str, Any], fallback_text: str) -> str:
    if not signal:
        return fallback_text

    script = signal.get("script") or "Unknown"
    direction = signal.get("position") or signal.get("side") or ""
    entry = signal.get("entry") or signal.get("enter_price") or signal.get("entryPrice")
    tps = signal.get("takeProfits") or signal.get("tps") or []
    sl = signal.get("stopLoss") or signal.get("sl")

    lines = []

    if INCLUDE_SCRIPT_LINE:
        lines.append(f"<b>{script}</b>")

    if direction:
        lines.append(f"Position: <b>{direction}</b>")
    if entry:
        lines.append(f"Entry: <code>{entry}</code>")

    if isinstance(tps, list) and tps:
        for idx, tp in enumerate(tps, start=1):
            lines.append(f"TP{idx}: <code>{tp}</code>")
    elif isinstance(tps, dict):
        for key, val in tps.items():
            lines.append(f"{key}: <code>{val}</code>")

    if sl:
        lines.append(f"SL: <code>{sl}</code>")

    if not lines:
        return fallback_text

    return "\n".join(lines)

def clean_signal_text(text: str) -> str:
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line_stripped = line.strip()
        line_lower = line_stripped.lower()

        # Drop promotional/contact-only lines
        if "wazir forex" in line_lower and "algo" in line_lower:
            continue
        if "inquiries" in line_lower and "dm" in line_lower:
            continue
        if "@zubarekhan" in line_lower:
            continue

        if line_stripped:
            cleaned_lines.append(line_stripped)

    return "\n".join(cleaned_lines).strip()


def should_block_message(text: str) -> bool:
    """
    Block only if, after stripping spam lines, nothing meaningful remains.
    """
    cleaned = clean_signal_text(text)
    return cleaned == ""

# ---------------------------------------------------------------------------
# Telegram Bot API
# ---------------------------------------------------------------------------

def send_telegram_message(
    chat_id: int,
    text: str,
    thread_id: Optional[int] = None,
    parse_mode: str = "HTML",
    reply_markup: Optional[Dict] = None,
) -> Optional[int]:
    """Returns message_id if successful"""
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN not set, cannot send message")
        return None

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if thread_id is not None:
        payload["message_thread_id"] = thread_id
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            logger.warning(
                "sendMessage failed for chat_id=%s: http=%s body=%s",
                chat_id,
                resp.status_code,
                resp.text[:200],
            )
            return None
        else:
            data = resp.json()
            msg_id = data.get("result", {}).get("message_id")
            logger.info("Sent message to chat_id=%s thread_id=%s msg_id=%s", chat_id, thread_id, msg_id)
            return msg_id
    except Exception as exc:
        logger.exception("Error sending Telegram message: %s", exc)
        return None

def send_approval_request(text: str, approval_id: str) -> None:
    """Send approval request with Allow/Deny buttons"""
    if not APPROVAL_CHAT_ID_INT:
        logger.warning("APPROVAL_CHAT_ID not set, cannot send approval request")
        return

    preview = text[:500] + ("..." if len(text) > 500 else "")
    
    message = (
        f"🔔 <b>New Unknown Message Format</b>\n\n"
        f"<i>Preview:</i>\n<code>{preview}</code>\n\n"
        f"Allow forwarding to groups + webhook?"
    )
    
    inline_keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Allow", "callback_data": f"approve_{approval_id}"},
                {"text": "❌ Deny", "callback_data": f"deny_{approval_id}"}
            ]
        ]
    }
    
    send_telegram_message(APPROVAL_CHAT_ID_INT, message, reply_markup=inline_keyboard)

def forward_to_all_destinations(formatted_text: str) -> None:
    if MAIN_CHAT_ID:
        send_telegram_message(MAIN_CHAT_ID, formatted_text, MAIN_THREAD_ID)

    if EXTRA1_CHAT_ID:
        send_telegram_message(EXTRA1_CHAT_ID, formatted_text, EXTRA1_THREAD_ID)

    if EXTRA2_CHAT_ID:
        send_telegram_message(EXTRA2_CHAT_ID, formatted_text, EXTRA2_THREAD_ID)

# ---------------------------------------------------------------------------
# Whop webhook
# ---------------------------------------------------------------------------

def send_whop_webhook(formatted_text: str, signal: Optional[Dict[str, Any]], raw_text: str) -> None:
    if not WEBHOOK_URL:
        logger.debug("WEBHOOK_URL not set, skipping webhook.")
        return

    if WEBHOOK_SEND_MODE == "json":
        payload: Any = {WEBHOOK_PAYLOAD_KEY: formatted_text}
        if WEBHOOK_INCLUDE_META:
            payload["meta"] = {
                "raw_text": raw_text,
                "signal": signal or {},
            }
        headers = {"Content-Type": "application/json"}
        data_to_send = payload
    elif WEBHOOK_SEND_MODE == "form":
        payload = {WEBHOOK_PAYLOAD_KEY: formatted_text}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data_to_send = payload
    else:
        payload = formatted_text
        headers = {"Content-Type": "text/plain"}
        data_to_send = payload

    if WEBHOOK_SHARED_SECRET:
        sig = f"{len(formatted_text)}:{WEBHOOK_SHARED_SECRET}"
        headers[WEBHOOK_SIGNATURE_HEADER] = sig

    if WEBHOOK_URL.startswith("http://") and not ALLOW_INSECURE_WEBHOOK:
        logger.warning("HTTP webhook blocked. URL=%s", WEBHOOK_URL)
        return

    try:
        if WEBHOOK_SEND_MODE == "json":
            resp = requests.post(WEBHOOK_URL, json=data_to_send, headers=headers, timeout=10)
        elif WEBHOOK_SEND_MODE == "form":
            resp = requests.post(WEBHOOK_URL, data=data_to_send, headers=headers, timeout=10)
        else:
            resp = requests.post(WEBHOOK_URL, data=data_to_send, headers=headers, timeout=10)

        if resp.status_code >= 400:
            logger.warning("Webhook failed: http=%s body=%s", resp.status_code, resp.text[:200])
        else:
            logger.info("Webhook sent successfully (status %s)", resp.status_code)
    except Exception as exc:
        logger.exception("Error sending webhook: %s", exc)

# ---------------------------------------------------------------------------
# Message processing
# ---------------------------------------------------------------------------

async def process_channel_message(event) -> None:
    message = event.message
    text = message.message or ""
    chat_id = event.chat_id

    logger.info("New channel message: id=%s chat_id=%s has_text=%s", message.id, chat_id, bool(text.strip()))

    if not text.strip():
        logger.info("Skipping message id=%s (no text).", message.id)
        return

    if should_block_message(text):
        logger.info("Skipping message id=%s (blocked by spam filter).", message.id)
        return

    if ALLOWED_CHAT_IDS and chat_id not in ALLOWED_CHAT_IDS:
        logger.info("Skipping chat_id=%s (not in ALLOWED_CHAT_IDS)", chat_id)
        return

    if REQUIRE_FORWARDED and not (message.fwd_from or getattr(message, "forward", None)):
        logger.info("Skipping message id=%s (REQUIRE_FORWARDED=true, not forwarded).", message.id)
        return

    if not is_forwarding_enabled():
        logger.info("Forwarding disabled (forward_state.json), but still calling Freya ingest.")
    else:
        logger.info("Forwarding is currently enabled.")

    # 1) Always send raw text to Freya ingest
    ingest_result = call_freya_ingest(text)

    # 2) Check if Freya recognized it
    is_valid_signal = ingest_result.get("success") and ingest_result.get("status") == "success"
    signal_obj: Dict[str, Any] = (ingest_result.get("data") or {}).get("signal", {}) if ingest_result.get("data") else {}

    if not is_forwarding_enabled():
        logger.info("Forwarding disabled – not sending anywhere.")
        return

    if is_valid_signal:
        # Known format - forward immediately
        logger.info("Message id=%s classified as VALID signal by Freya - forwarding immediately", message.id)
        
        cleaned_text = clean_signal_text(text)
        
        if signal_obj and signal_obj.get("symbol"):
            logger.info("Using formatted version")
            formatted_text = build_signal_text(signal_obj, text)
            final_text = clean_signal_text(formatted_text)
        else:
            logger.info("Using cleaned raw text")
            final_text = cleaned_text
        
        forward_to_all_destinations(final_text)
        send_whop_webhook(final_text, signal_obj, raw_text=text)
    else:
        # Unknown format - request approval
        logger.info("Message id=%s NOT recognized by Freya - requesting approval", message.id)
        approval_id = add_pending_approval(text, signal_obj)
        send_approval_request(text, approval_id)

# ---------------------------------------------------------------------------
# Main Telethon client
# ---------------------------------------------------------------------------

async def main() -> None:
    print("=" * 60)
    print("🚀 user_forwarder.py (Telethon userbot with approval system)")
    print("=" * 60)
    print(f"👤 Session: {SESSION_NAME}")
    print(f"📺 Source channel: {SOURCE_CHANNEL}")
    print(f"📡 Freya API: {WEBSITE_API_URL or 'not configured'}")
    print(f"🔐 Ingest key set: {'yes' if INGEST_API_KEY else 'no'}")
    print(f"🎯 Main group: {MAIN_CHAT_ID} thread={MAIN_THREAD_ID}")
    print(f"🎯 Extra1: {EXTRA1_CHAT_ID} thread={EXTRA1_THREAD_ID}")
    print(f"🎯 Extra2: {EXTRA2_CHAT_ID} thread={EXTRA2_THREAD_ID}")
    print(f"✅ Approval chat: {APPROVAL_CHAT_ID_INT}")
    print("=" * 60)

    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    async with client:
        try:
            channel_entity = await client.get_entity(SOURCE_CHANNEL)
            try:
                await client(JoinChannelRequest(channel_entity))
                logger.info("Joined channel %s", SOURCE_CHANNEL)
            except Exception:
                logger.info("Could not join channel (possibly already joined).")
        except (ChannelInvalidError, ChannelPrivateError) as exc:
            logger.error("Cannot resolve/join SOURCE_CHANNEL %s: %s", SOURCE_CHANNEL, exc)
            return

        @client.on(events.NewMessage(chats=SOURCE_CHANNEL, incoming=True))
        async def handler(event):
            try:
                await process_channel_message(event)
            except Exception as exc:
                logger.exception("Error in handler: %s", exc)

        logger.info("User forwarder is running. Waiting for messages...")
        await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
