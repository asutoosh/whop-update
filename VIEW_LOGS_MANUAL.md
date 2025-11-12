# How to View Logs When Running Manually

## When Running `python3 run_bots.py`

The logs appear **directly in your terminal** where you ran the command.

### Step 1: Run the Bots

```bash
cd ~/whop-update
python3 run_bots.py
```

You should see output like:
```
INFO:launcher:Starting both bots...
INFO:launcher:Forwarder bot process started (PID: 12345)
INFO:launcher:User forwarder process started (PID: 12346)
INFO:forwarder_bot:Bot started. Waiting for forwarded messages...
INFO:user_forwarder:Listening as user session...
```

### Step 2: Keep Terminal Open

**Keep this terminal window open** - all logs will appear here in real-time.

### Step 3: Click the Button and Watch

When you click "Allow Forward ✅" or "Deny 🚫" in Telegram, you should immediately see logs in your terminal like:

```
INFO:forwarder_bot:Callback query received: from_user=123456789, chat=-1001234567890, data=allow|-1003200388027:38
INFO:forwarder_bot:Processing callback: action=allow, key=-1003200388027:38
INFO:forwarder_bot:Pending store lookup: key=-1003200388027:38, found=False
INFO:forwarder_bot:Pending forward not found for key=-1003200388027:38, trying to extract from message
INFO:forwarder_bot:Extracting text from approval message: Ready to forward this message?...
```

---

## What to Look For

### ✅ Good Signs:
- You see "Callback query received" when clicking
- You see "Processing callback: action=allow/deny"
- You see "Extracting text from approval message"
- You see "Webhook accepted message status=200" (for Allow)

### ❌ Bad Signs:
- **No logs appear when clicking** → Bot not receiving callbacks
- **"User X is not in APPROVER_IDS"** → Add your user ID to `.env`
- **"Callback query has no data"** → Button data issue
- **No "Callback query received" at all** → Bot might not be running or not receiving updates

---

## If You Don't See Any Logs When Clicking

### Check 1: Is the Bot Running?

Look at your terminal - you should see:
```
INFO:forwarder_bot:Bot started. Waiting for forwarded messages...
```

If you don't see this, the bot might have crashed. Check for error messages.

### Check 2: Is the Bot Receiving Updates?

The bot needs to be **polling** (actively checking for updates). You should see periodic activity or at least the "Bot started" message.

### Check 3: Check for Errors

Scroll up in your terminal to see if there are any ERROR messages.

---

## Alternative: Run in Background and Check Logs

If you want to run it in the background and still see logs:

### Option A: Use `screen` or `tmux`

```bash
# Install screen if not installed
apt install screen -y

# Start a screen session
screen -S bots

# Run your bots
cd ~/whop-update
python3 run_bots.py

# Detach: Press Ctrl+A then D
# Reattach later: screen -r bots
```

### Option B: Redirect Output to File

```bash
cd ~/whop-update
python3 run_bots.py > bot_logs.txt 2>&1 &

# Watch logs in real-time
tail -f bot_logs.txt
```

### Option C: Use systemd (Recommended for Production)

```bash
# Set up systemd service (see DROPLET_SETUP.md)
systemctl start tg-forwarder

# View logs
journalctl -u tg-forwarder -f
```

---

## Quick Test

1. **Run the bots:**
   ```bash
   python3 run_bots.py
   ```

2. **Keep terminal open and watch it**

3. **Send a test message** that needs approval

4. **Click "Allow Forward ✅"** in Telegram

5. **Immediately check your terminal** - you should see logs appear

If you see logs → Good! The bot is receiving callbacks.
If you see nothing → The bot might not be receiving the callback query.

---

## Common Issues

### Issue: "No logs appear when clicking"

**Possible causes:**
- Bot is not running (check terminal)
- Bot is not polling for updates
- Network issue
- Bot token is wrong

**Fix:**
- Make sure the terminal shows "Bot started"
- Check for any error messages
- Verify BOT_TOKEN in `.env` is correct

### Issue: "User X is not in APPROVER_IDS"

**Fix:**
- Get your user ID from @userinfobot
- Add it to `APPROVER_IDS` in `.env`
- Restart the bots

---

## Need More Help?

Share what you see in your terminal when:
1. You start the bots
2. You click the Allow/Deny button

This will help identify the exact issue!

