# Setting Up Private Channel for Approval Requests

## What You Need

Since you created a **private channel**, you need to use the **numeric channel ID** (not username).

---

## Step 1: Get Your Private Channel ID

### Method 1: Using the Helper Script (Easiest)

On your droplet:

```bash
cd ~/whop-update
git pull

# If your channel has a username:
python3 get_channel_id.py @your_channel_username

# If your channel doesn't have a username, you need to:
# 1. Forward a message from the channel to @userinfobot
# 2. Or use Method 2 below
```

### Method 2: Using @userinfobot

1. **Forward a message from your private channel to [@userinfobot](https://t.me/userinfobot)**
   - Go to your private channel
   - Long press any message
   - Forward it to @userinfobot
   - The bot will reply with the channel ID (negative number like `-1001234567890`)

### Method 3: Check Bot Logs

1. **Send a test message in your private channel**
2. **Check your bot logs:**
   ```bash
   journalctl -u tg-forwarder -f
   ```
   - Look for chat_id in the logs when the bot receives a message

---

## Step 2: Update Your .env File

Once you have the channel ID (negative number like `-1001234567890`):

```bash
cd ~/whop-update
nano .env
```

**Find this line:**
```
APPROVAL_CHAT_ID=@forwaaarddddfffoooorrrrrmmmeebot
```

**Change it to your channel ID:**
```
APPROVAL_CHAT_ID=-1001234567890
```

(Replace `-1001234567890` with your actual channel ID)

**Save:** `Ctrl + X`, then `Y`, then `Enter`

---

## Step 3: Verify Bot is Admin

Make sure your bot is an admin of the private channel:

1. Go to your private channel
2. Click channel name → "Administrators"
3. Verify your bot is listed
4. Make sure it has permission to "Post Messages"

---

## Step 4: Restart the Bots

```bash
systemctl restart tg-forwarder
```

Or test manually:
```bash
python3 run_bots.py
```

---

## Step 5: Test

1. Send a test message to your monitored channel that needs approval
2. Check your private channel - you should see the approval request
3. Click "Allow Forward ✅" - it should work!

---

## Important Notes

- **Private channels** don't have usernames (usually), so you MUST use the numeric ID
- The ID will be a **negative number** like `-1001234567890`
- The bot **must be an admin** of the channel
- The bot needs permission to **post messages**

---

## Troubleshooting

**If you still get "chat not found":**
- Double-check the channel ID is correct (negative number)
- Make sure the bot is an admin
- Try sending a test message from the bot manually to the channel first

**If buttons don't work:**
- Make sure the bot is listening (check logs)
- The callback handler should work from any chat where the bot receives callbacks

