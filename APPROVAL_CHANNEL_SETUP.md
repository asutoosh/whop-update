# Setting Up Approval Channel

## What You Want

- Approval requests should go to: `@forwaaarddddfffoooorrrrrmmmeebot` (your bot channel)
- Allow/Deny buttons should work in that channel
- Currently going to subtopic group instead

## Changes Made

1. ✅ Updated `user_forwarder.py` to support channel usernames (like `@forwaaarddddfffoooorrrrrmmmeebot`)
2. ✅ Fixed logic to not add thread_id when sending to a different channel
3. ✅ Callback handler already works for any chat (no changes needed)

## What You Need to Do

### Step 1: Update Your .env File

On your droplet, edit `.env`:

```bash
nano .env
```

**Change this line:**
```
APPROVAL_CHAT_ID=-1003200388027
```

**To:**
```
APPROVAL_CHAT_ID=@forwaaarddddfffoooorrrrrmmmeebot
```

**Save:** `Ctrl + X`, then `Y`, then `Enter`

### Step 2: Make Sure Your Bot is in the Channel

1. **Add your bot to the channel** `@forwaaarddddfffoooorrrrrmmmeebot`
   - Go to the channel
   - Click channel name → "Administrators" → "Add Administrator"
   - Search for your bot username and add it
   - Give it permission to "Post Messages"

2. **Verify the bot can send messages:**
   - The bot needs to be able to post in the channel
   - Test by having the bot send a message manually

### Step 3: Pull Updated Code and Restart

```bash
cd ~/whop-update
git pull
systemctl restart tg-forwarder
```

Or if testing manually:
```bash
python3 run_bots.py
```

## How It Works Now

1. **When a message needs approval:**
   - `user_forwarder.py` sends approval request to `@forwaaarddddfffoooorrrrrmmmeebot`
   - The message includes Allow/Deny buttons

2. **When you click Allow/Deny:**
   - `forwarder_bot.py` receives the callback query
   - It processes the approval/denial
   - Sends to webhook if approved

3. **The buttons work because:**
   - Callback queries work from any chat where the bot receives them
   - The bot is listening to all callbacks via `CallbackQueryHandler`

## Testing

1. Send a test message to your monitored channel that doesn't match auto-forward criteria
2. Check `@forwaaarddddfffoooorrrrrmmmeebot` - you should see the approval request
3. Click "Allow Forward ✅" - it should forward to webhook
4. Click "Deny 🚫" - it should deny the forward

## Troubleshooting

**If approval requests still go to subtopic group:**
- Check that `APPROVAL_CHAT_ID=@forwaaarddddfffoooorrrrrmmmeebot` in `.env`
- Make sure you restarted the bots after changing `.env`

**If buttons don't work:**
- Make sure your bot is added to `@forwaaarddddfffoooorrrrrmmmeebot` as admin
- Check bot logs: `journalctl -u tg-forwarder -f`
- Verify the bot can receive callbacks (check logs when clicking buttons)

**If you get "chat not found":**
- Make sure the channel username is correct: `@forwaaarddddfffoooorrrrrmmmeebot`
- Make sure your bot is added to the channel
- The channel must be public or the bot must be a member

