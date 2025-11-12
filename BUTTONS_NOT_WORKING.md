# Fix: Allow/Deny Buttons Not Working

## Common Issues and Fixes

### Issue 1: Your User ID Not in APPROVER_IDS

**Symptom:** Buttons don't respond or show "You are not allowed to approve forwards"

**Fix:**

1. **Get your Telegram user ID:**
   - Send a message to [@userinfobot](https://t.me/userinfobot)
   - It will reply with your user ID (a number like `123456789`)

2. **Update your `.env` file:**
   ```bash
   nano .env
   ```
   
   Find:
   ```
   APPROVER_IDS=1977988206
   ```
   
   Add your user ID (comma-separated if multiple):
   ```
   APPROVER_IDS=1977988206,123456789
   ```
   
   (Replace `123456789` with your actual user ID)

3. **Restart:**
   ```bash
   systemctl restart tg-forwarder
   ```

---

### Issue 2: Check Bot Logs

The updated code now has detailed logging. Check what's happening:

```bash
journalctl -u tg-forwarder -f
```

When you click a button, you should see:
- `Callback query received: from_user=...`
- `Processing callback: action=allow/deny, key=...`
- `Pending store lookup: key=..., found=True/False`

**What to look for:**
- If you see "User X is not in APPROVER_IDS" → Fix Issue 1
- If you see "Pending forward not found" → The fallback extraction should still work
- If you see nothing → The bot might not be receiving callbacks

---

### Issue 3: Bot Not Receiving Callbacks

**Check:**
1. Is the bot running? `systemctl status tg-forwarder`
2. Is the bot polling? Check logs for "Bot started. Waiting for forwarded messages..."
3. Is the bot token correct in `.env`?

**Fix:**
```bash
# Restart the bot
systemctl restart tg-forwarder

# Check logs
journalctl -u tg-forwarder -f
```

---

### Issue 4: Callback Data Format Mismatch

The callback data format is: `allow|{chat_id}:{message_id}` or `deny|{chat_id}:{message_id}`

**Check logs** to see what the actual callback data is when you click.

---

## Quick Diagnostic Steps

1. **Pull latest code:**
   ```bash
   cd ~/whop-update
   git pull
   systemctl restart tg-forwarder
   ```

2. **Check your user ID is in APPROVER_IDS:**
   ```bash
   cat .env | grep APPROVER_IDS
   ```

3. **Watch logs while clicking button:**
   ```bash
   journalctl -u tg-forwarder -f
   ```
   Then click Allow/Deny and see what appears in logs

4. **Test manually:**
   - Send a test message that needs approval
   - Click the button
   - Check logs for any errors

---

## Expected Behavior

When you click "Allow Forward ✅":
- Button should show a loading state
- Message should update to "✅ Forwarded."
- Webhook should receive the message
- Logs should show: "Webhook accepted message status=200"

When you click "Deny 🚫":
- Button should show a loading state
- Message should update to "🚫 Forward denied."
- Logs should show: "Forward denied"

---

## Still Not Working?

1. **Check logs first** - they will tell you exactly what's wrong
2. **Verify your user ID** is in APPROVER_IDS
3. **Make sure bot is running** and receiving updates
4. **Try restarting** the bot service

The new logging will help identify the exact issue!

