#!/usr/bin/env python3
"""
List all channels/groups you have access to and show their IDs.
Useful for finding your private channel ID.
"""

import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("USERBOT_SESSION", "user_forwarder")

if not API_ID or not API_HASH:
    print("ERROR: API_ID and API_HASH must be set in .env")
    exit(1)

async def main():
    api_id = int(API_ID)
    api_hash = API_HASH
    
    async with TelegramClient(SESSION_NAME, api_id, api_hash) as client:
        print("\n📋 Listing all your channels and groups...\n")
        
        try:
            # Get all dialogs (chats, channels, groups)
            dialogs = await client.get_dialogs()
            
            channels = []
            groups = []
            
            for dialog in dialogs:
                entity = dialog.entity
                if hasattr(entity, 'broadcast') and entity.broadcast:
                    # It's a channel
                    channels.append({
                        'title': getattr(entity, 'title', 'N/A'),
                        'id': entity.id,
                        'username': getattr(entity, 'username', None),
                        'is_admin': getattr(dialog, 'is_admin', False)
                    })
                elif hasattr(entity, 'megagroup') and entity.megagroup:
                    # It's a supergroup
                    groups.append({
                        'title': getattr(entity, 'title', 'N/A'),
                        'id': entity.id,
                        'username': getattr(entity, 'username', None),
                        'is_admin': getattr(dialog, 'is_admin', False)
                    })
            
            if channels:
                print("📺 CHANNELS:")
                print("=" * 60)
                for ch in channels:
                    username_str = f"@{ch['username']}" if ch['username'] else "(no username - private)"
                    admin_str = " [ADMIN]" if ch['is_admin'] else ""
                    # Convert to Bot API format for channels
                    telethon_id = ch['id']
                    if telethon_id > 0:
                        bot_api_id = int(f"-100{telethon_id}")
                    else:
                        bot_api_id = telethon_id
                    print(f"  Title: {ch['title']}")
                    print(f"  Telethon ID: {telethon_id}")
                    print(f"  Bot API ID: {bot_api_id}  ⬅️ USE THIS IN .env")
                    print(f"  Username: {username_str}{admin_str}")
                    print()
            
            if groups:
                print("\n👥 GROUPS:")
                print("=" * 60)
                for grp in groups:
                    username_str = f"@{grp['username']}" if grp['username'] else "(no username - private)"
                    admin_str = " [ADMIN]" if grp['is_admin'] else ""
                    # Convert to Bot API format for supergroups
                    telethon_id = grp['id']
                    if telethon_id > 0:
                        bot_api_id = int(f"-100{telethon_id}")
                    else:
                        bot_api_id = telethon_id
                    print(f"  Title: {grp['title']}")
                    print(f"  Telethon ID: {telethon_id}")
                    print(f"  Bot API ID: {bot_api_id}  ⬅️ USE THIS IN .env")
                    print(f"  Username: {username_str}{admin_str}")
                    print()
            
            if not channels and not groups:
                print("No channels or groups found.")
            
            print("\n" + "=" * 60)
            print("📝 To use a channel/group in your .env file:")
            print("   Use the 'Bot API ID' shown above (the -100xxxxxxxxxx format)")
            print("   Example:")
            print("   FORWARD_TO_CHAT_ID=-1003390558581")
            print("   APPROVAL_CHAT_ID=-1003390558581")
            print()
            
        except Exception as exc:
            print(f"\n❌ Error: {exc}")
            print()

if __name__ == "__main__":
    asyncio.run(main())

