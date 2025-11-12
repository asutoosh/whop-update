# Fix: Forwarder Bot Crashed - Buttons Not Working

## The Problem

Your forwarder bot is **crashing on startup** with this error:
```
AttributeError: 'Updater' object has no attribute '_Updater_polling_cleanup_cb'
```

This is a **Python 3.13 compatibility issue** with `python-telegram-bot 20.7`.

**Result:** The bot crashes, so it can't receive callback queries → buttons don't work!

---

## The Fix

### Option 1: Upgrade python-telegram-bot (Recommended)

The newer version supports Python 3.13:

```bash
cd ~/whop-update
git pull

# If using virtual environment:
source venv/bin/activate
pip install --upgrade "python-telegram-bot[rate-limiter]>=21.0"

# If using system-wide:
pip3 install --upgrade "python-telegram-bot[rate-limiter]>=21.0" --break-system-packages
```

Then restart:
```bash
python3 run_bots.py
```

### Option 2: Use Python 3.11 or 3.12 (If upgrade doesn't work)

If upgrading doesn't work, you can use an older Python version:

```bash
# Install Python 3.12
apt install python3.12 python3.12-venv -y

# Create new virtual environment with Python 3.12
cd ~/whop-update
python3.12 -m venv venv312
source venv312/bin/activate
pip install -r requirements.txt

# Run with Python 3.12
python3.12 run_bots.py
```

---

## After Fixing

1. **Start the bots:**
   ```bash
   python3 run_bots.py
   ```

2. **Check for this message:**
   ```
   INFO:forwarder_bot:Bot started. Waiting for forwarded messages...
   ```
   
   If you see this, the bot is running! ✅

3. **Test the buttons:**
   - Send a message that needs approval
   - Click "Allow Forward ✅" or "Deny 🚫"
   - You should see logs in terminal when clicking
   - The buttons should work!

---

## Verify It's Fixed

After restarting, you should see:
- ✅ `INFO:forwarder_bot:Bot started. Waiting for forwarded messages...`
- ✅ No error messages
- ✅ When you click buttons, logs appear in terminal

If you still see the AttributeError, try Option 2 (use Python 3.12).

---

## Quick Commands

```bash
# Pull latest code (I've updated requirements.txt)
cd ~/whop-update
git pull

# Upgrade the library
source venv/bin/activate  # if using venv
pip install --upgrade "python-telegram-bot[rate-limiter]>=21.0"

# Restart
python3 run_bots.py
```

The bot should start without crashing, and then your buttons will work!

