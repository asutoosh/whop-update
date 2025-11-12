# How to Get Your Real Chat ID

The error shows you're still using the placeholder chat ID: `-1001234567890`

You need to replace it with your **REAL chat ID**.

---

## Method 1: Using @userinfobot (Easiest)

1. **Add [@userinfobot](https://t.me/userinfobot) to your group/channel**
   - Go to your Telegram group
   - Click on group name → "Add Members"
   - Search for `@userinfobot` and add it

2. **Send any message in the group**
   - Type anything and send it

3. **The bot will reply with chat information**
   - It will show: `Chat ID: -1001234567890` (your real ID will be different)
   - Copy that number

---

## Method 2: Using Your Bot (If bot is already in group)

1. **Make sure your bot is added to the group as admin**

2. **Send a test message in the group**

3. **Check your bot logs on the droplet:**
   ```bash
   journalctl -u tg-forwarder -f
   ```
   - You'll see the chat_id in the logs

---

## Method 3: Using Telegram Web (Sometimes works)

1. Open https://web.telegram.org
2. Go to your group
3. Sometimes the chat ID appears in the URL or page source

---

## Method 4: Using a Simple Bot Script

Create a temporary test script on your droplet:

```bash
cd ~/whop-update
nano get_chat_id.py
```

Paste this:
```python
import os
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))

async def main():
    updates = await bot.get_updates()
    for update in updates:
        if update.message:
            chat = update.message.chat
            print(f"Chat Title: {chat.title}")
            print(f"Chat ID: {chat.id}")
            print(f"Chat Type: {chat.type}")
            print("---")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

Run it:
```bash
python3 get_chat_id.py
```

Then send a message to your bot or in your group, and run the script again.

---

## After Getting Your Chat ID

1. **Edit your `.env` file:**
   ```bash
   cd ~/whop-update
   nano .env
   ```

2. **Find and update these lines:**
   ```
   FORWARD_TO_CHAT_ID=-1001234567890  ← Replace with YOUR real chat ID
   APPROVAL_CHAT_ID=-1001234567890    ← Usually same as FORWARD_TO_CHAT_ID
   ```

3. **If using forum topics, also update:**
   ```
   FORWARD_TO_THREAD_ID=7  ← Replace with YOUR real thread ID
   ```

4. **Save:** `Ctrl + X`, then `Y`, then `Enter`

5. **Restart your bots:**
   ```bash
   # If using systemd:
   systemctl restart tg-forwarder
   
   # Or if testing manually:
   python3 run_bots.py
   ```

---

## Important Notes

- **Chat IDs are negative numbers** for groups/channels (like `-1001234567890`)
- **Make sure your bot is added to the group** before trying to send messages
- **The bot needs to be an admin** if you want it to send messages to topics
- **Thread ID** is only needed if forwarding to forum topics (usually 1, 2, 3, etc.)

---

## Quick Test

After updating, test by sending a message to your monitored channel. Check logs:
```bash
journalctl -u tg-forwarder -f
```

You should see successful message processing without "chat not found" errors!

