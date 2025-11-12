#!/usr/bin/env python3
"""
Helper script to get channel ID from username.
Run this on your droplet to get the numeric ID for your approval channel.
"""

import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("USERBOT_SESSION", "user_forwarder")
CHANNEL_USERNAME = os.getenv("APPROVAL_CHAT_ID", "@forwaaarddddfffoooorrrrrmmmeebot")

if not API_ID or not API_HASH:
    print("ERROR: API_ID and API_HASH must be set in .env")
    exit(1)

async def main():
    api_id = int(API_ID)
    api_hash = API_HASH
    
    async with TelegramClient(SESSION_NAME, api_id, api_hash) as client:
        try:
            # Remove @ if present
            username = CHANNEL_USERNAME.lstrip("@")
            entity = await client.get_entity(username)
            
            print(f"\n✅ Channel found!")
            print(f"   Username: @{username}")
            print(f"   Title: {getattr(entity, 'title', 'N/A')}")
            print(f"   ID: {entity.id}")
            print(f"\n📝 Use this in your .env file:")
            print(f"   APPROVAL_CHAT_ID={entity.id}")
            print()
        except Exception as exc:
            print(f"\n❌ Error: {exc}")
            print(f"\nMake sure:")
            print(f"  1. The channel username is correct: {CHANNEL_USERNAME}")
            print(f"  2. Your userbot session has access to the channel")
            print(f"  3. The channel exists and is accessible")
            print()

if __name__ == "__main__":
    asyncio.run(main())

