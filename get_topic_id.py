#!/usr/bin/env python3
"""
Helper script to find topic IDs (message_thread_id) for groups.
This will show you the chat_id and topic_id for messages sent in forum topics.

Instructions:
1. Make sure your bots are STOPPED (run_bots.py not running)
2. Go to the topic (subgroup) in Telegram
3. Send a test message in that topic (e.g., "test topic")
4. Run this script: python get_topic_id.py
5. Look for the topic you want and copy the IDs shown
"""

import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ ERROR: BOT_TOKEN not found in .env file")
    print("   Make sure you have BOT_TOKEN=... in your .env file")
    exit(1)

print("\n" + "=" * 60)
print("🔍 Finding Topic IDs for Groups")
print("=" * 60)
print("\n📋 Instructions:")
print("   1. Make sure run_bots.py is NOT running (stop it first!)")
print("   2. Go to your group topic in Telegram")
print("   3. Send a test message in that topic")
print("   4. Run this script again")
print("\n⏳ Fetching updates from Telegram...\n")

try:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    
    if not data.get("ok"):
        print(f"❌ Telegram API error: {data.get('description', 'Unknown error')}")
        exit(1)
    
    updates = data.get("result", [])
    
    if not updates:
        print("⚠️  No updates found!")
        print("\n💡 This usually means:")
        print("   - Your bots (run_bots.py) are still running - STOP THEM FIRST!")
        print("   - OR you haven't sent a test message yet")
        print("   - OR the bot hasn't received any messages")
        print("\n📝 Steps:")
        print("   1. Stop run_bots.py (Ctrl+C or systemctl stop tg-forwarder)")
        print("   2. Go to your group topic in Telegram")
        print("   3. Send a message like 'test' in that topic")
        print("   4. Run this script again")
        print()
        exit(0)
    
    print(f"✅ Found {len(updates)} update(s)\n")
    print("=" * 60)
    print("📊 TOPIC INFORMATION:")
    print("=" * 60)
    
    found_topics = []
    
    for update in updates:
        message = update.get("message") or update.get("edited_message")
        if not message:
            continue
        
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        chat_title = chat.get("title", "Unknown")
        chat_type = chat.get("type", "unknown")
        message_thread_id = message.get("message_thread_id")
        text = message.get("text", message.get("caption", ""))
        
        # Only show group/supergroup messages with topics
        if chat_type in ("group", "supergroup"):
            topic_info = {
                "chat_id": chat_id,
                "chat_title": chat_title,
                "thread_id": message_thread_id,
                "text_preview": text[:50] if text else "(no text)",
            }
            found_topics.append(topic_info)
    
    if not found_topics:
        print("\n⚠️  No group messages with topics found!")
        print("\n💡 Make sure:")
        print("   - You sent a message in a GROUP (not a channel)")
        print("   - The group has topics/forums enabled")
        print("   - You sent the message INSIDE a topic (not in general)")
        print()
        exit(0)
    
    # Show results
    for idx, topic in enumerate(found_topics, 1):
        print(f"\n📌 Topic #{idx}:")
        print(f"   Group: {topic['chat_title']}")
        print(f"   Chat ID: {topic['chat_id']}")
        if topic['thread_id']:
            print(f"   Topic ID: {topic['thread_id']}")
        else:
            print(f"   Topic ID: (none - this is general chat, not a topic)")
        print(f"   Message preview: {topic['text_preview']}")
    
    print("\n" + "=" * 60)
    print("📝 COPY THESE TO YOUR .env FILE:")
    print("=" * 60)
    
    # Show .env format
    for idx, topic in enumerate(found_topics, 1):
        if topic['thread_id']:  # Only show if it's actually a topic
            print(f"\n# For: {topic['chat_title']}")
            print(f"EXTRA_FORWARD_{idx}_CHAT_ID={topic['chat_id']}")
            print(f"EXTRA_FORWARD_{idx}_THREAD_ID={topic['thread_id']}")
    
    print("\n" + "=" * 60)
    print("✅ Done! Copy the values above to your .env file")
    print("=" * 60)
    print()
    
    # Clear updates so next run is clean
    if updates:
        last_update_id = updates[-1].get("update_id")
        if last_update_id:
            clear_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}"
            requests.get(clear_url, timeout=5)
            print("🧹 Cleared processed updates (so next run shows new messages)")
            print()

except requests.exceptions.RequestException as e:
    print(f"❌ Network error: {e}")
    print("   Check your internet connection and BOT_TOKEN")
    exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

