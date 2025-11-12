# Fix: Bots Can't Send Messages to Bots

## The Problem

The error `"Forbidden: bots can't send messages to bots"` means:
- `@forwaaarddddfffoooorrrrrmmmeebot` is your **bot's username**
- When resolved, it becomes your **bot's ID** (8494323944)
- Bots cannot send messages to themselves

## The Solution

You need the **CHANNEL's ID**, not the bot's ID!

### Step 1: Find Your Channel

If `@forwaaarddddfffoooorrrrrmmmeebot` is a **channel** (not just a bot):
1. Go to the channel in Telegram
2. The channel should have a username like `@forwaaarddddfffoooorrrrrmmmeebot`
3. Your bot should be an admin of this channel

### Step 2: Get the Channel ID

**Option A: Using the helper script**

On your droplet:
```bash
cd ~/whop-update
git pull
python3 get_channel_id.py @forwaaarddddfffoooorrrrrmmmeebot
```

This will show you the channel ID (a negative number like `-1001234567890`).

**Option B: Using @userinfobot**

1. Add [@userinfobot](https://t.me/userinfobot) to your channel
2. Send any message in the channel
3. The bot will reply with the channel ID

**Option C: Check if it's actually a channel**

If `@forwaaarddddfffoooorrrrrmmmeebot` is just a bot (not a channel), you need to:
1. Create a **channel** (not a bot)
2. Add your bot as an admin to that channel
3. Use that channel's ID for `APPROVAL_CHAT_ID`

### Step 3: Update Your .env

Once you have the channel ID (negative number):

```bash
nano .env
```

Change:
```
APPROVAL_CHAT_ID=@forwaaarddddfffoooorrrrrmmmeebot
```

To the numeric channel ID:
```
APPROVAL_CHAT_ID=-1001234567890
```

(Replace `-1001234567890` with your actual channel ID)

Save: `Ctrl + X`, then `Y`, then `Enter`

### Step 4: Make Sure Bot is Admin

1. Go to your channel
2. Click channel name → "Administrators"
3. Make sure your bot is listed as admin
4. Give it permission to "Post Messages"

### Step 5: Restart

```bash
systemctl restart tg-forwarder
```

---

## Important Notes

- **Channel ID** = Negative number like `-1001234567890`
- **Bot ID** = Positive number like `8494323944` (this won't work!)
- The channel must exist and your bot must be an admin
- Bots cannot send messages to themselves or other bots

---

## Quick Check

If you're not sure if `@forwaaarddddfffoooorrrrrmmmeebot` is a channel or just a bot:

1. Try to open it in Telegram
2. If it's a **channel**: You'll see posts/messages, and you can add admins
3. If it's just a **bot**: You can only chat with it, no posts visible

If it's just a bot, you need to create a separate channel for approval requests!

