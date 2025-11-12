# Deployment Guide for DigitalOcean

This guide explains how to deploy your Telegram forwarder bots to DigitalOcean.

## 📋 What You Need Before Starting

1. **Telegram Bot Token** - Get from [@BotFather](https://t.me/BotFather)
2. **Telegram API Credentials** - Get from [my.telegram.org/apps](https://my.telegram.org/apps)
3. **Webhook URL** - Your endpoint that will receive the forwarded messages (must be HTTPS)
4. **DigitalOcean Account** - With a Droplet or App Platform setup

---

## 🔐 Understanding the Security Features

### 1. **Webhook Signing (Optional but Recommended)**

**What it is:** A way to prove that messages are really coming from your bot, not from an attacker.

**How it works:**
- You set a secret password (`WEBHOOK_SHARED_SECRET`)
- The bot signs every message with this secret
- Your webhook receiver checks the signature to verify authenticity

**Do you need it?** 
- ✅ **YES** if your webhook is public-facing or handles sensitive data
- ❌ **NO** if your webhook is private/internal only

**How to set it up:**
1. Generate a random secret (e.g., `openssl rand -hex 32`)
2. Set `WEBHOOK_SHARED_SECRET=your_secret` in your `.env`
3. Configure your webhook receiver to check the `X-Webhook-Signature` header

**Example validation code (for your webhook receiver):**
```python
import hmac
import hashlib

def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 2. **HTTPS Requirement**

**What it is:** The bot only sends to HTTPS webhooks (secure connections) by default.

**Why:** Prevents attackers from intercepting your messages.

**Exception:** If you're testing locally, you can set `ALLOW_INSECURE_WEBHOOK=true`, but **NEVER do this in production!**

---

## 🚀 Step-by-Step Deployment

### Step 1: Prepare Your Files

1. **Copy `.env.example` to `.env`** and fill in your values:
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

2. **Make sure `.gitignore` is in place** (already created) - this prevents committing secrets

### Step 2: Set Up DigitalOcean

#### Option A: DigitalOcean App Platform (Easier)

1. Go to DigitalOcean → App Platform
2. Create a new app → "GitHub" or "Upload Code"
3. **Environment Variables:** Add all variables from your `.env` file
   - Click "Edit" → "Environment Variables"
   - Add each variable one by one (e.g., `BOT_TOKEN`, `API_ID`, etc.)
4. **Build Command:** `pip install -r requirements.txt`
5. **Run Command:** `python run_bots.py`
6. **Session File:** Upload `user_forwarder.session` as a file or use DO's persistent storage

#### Option B: DigitalOcean Droplet (More Control)

1. Create a Droplet (Ubuntu 22.04 recommended)
2. SSH into your droplet:
   ```bash
   ssh root@your_droplet_ip
   ```
3. Install Python and dependencies:
   ```bash
   apt update
   apt install -y python3 python3-pip git
   ```
4. Clone your code (or upload via SCP):
   ```bash
   git clone your_repo_url
   cd your_repo
   ```
5. Install Python packages:
   ```bash
   pip3 install -r requirements.txt
   ```
6. Create `.env` file:
   ```bash
   nano .env
   # Paste your environment variables
   ```
7. Upload your session file:
   ```bash
   # Use SCP from your local machine:
   scp user_forwarder.session root@your_droplet_ip:/path/to/your/repo/
   ```

### Step 3: Run Your Bots

#### For App Platform:
- Just deploy! It will run automatically.

#### For Droplet:
Use a process manager like `systemd` or `screen`:

**Using screen (simple):**
```bash
screen -S bots
python3 run_bots.py
# Press Ctrl+A then D to detach
```

**Using systemd (recommended for production):**
Create `/etc/systemd/system/tg-forwarder.service`:
```ini
[Unit]
Description=Telegram Forwarder Bots
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/your/repo
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /path/to/your/repo/run_bots.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
systemctl enable tg-forwarder
systemctl start tg-forwarder
systemctl status tg-forwarder  # Check if running
```

---

## ✅ Environment Variables Checklist

Make sure you've set these in DigitalOcean (App Platform) or in your `.env` (Droplet):

**Required:**
- ✅ `BOT_TOKEN` - Your Telegram bot token
- ✅ `API_ID` - Telegram API ID
- ✅ `API_HASH` - Telegram API hash
- ✅ `SOURCE_CHANNEL` - Channel to monitor
- ✅ `FORWARD_TO_CHAT_ID` - Destination chat ID
- ✅ `WEBHOOK_URL` - Your webhook endpoint

**Optional but Recommended:**
- ✅ `WEBHOOK_SHARED_SECRET` - For webhook signing
- ✅ `APPROVER_IDS` - User IDs that can approve forwards
- ✅ `FORWARD_TO_THREAD_ID` - If forwarding to a forum topic

**Optional:**
- `ALLOWED_CHAT_IDS` - Restrict to specific chats
- `ALLOWED_TOPICS` - Restrict to specific topics
- `LOG_LEVEL` - Set to INFO for production

---

## 🧪 Testing Before Production

1. **Test locally first:**
   ```bash
   python run_bots.py
   ```
   Check that both bots start without errors.

2. **Test webhook signing (if enabled):**
   - Send a test message through your bot
   - Check your webhook logs to see if the `X-Webhook-Signature` header is present
   - Verify the signature matches

3. **Monitor logs:**
   ```bash
   # On Droplet:
   journalctl -u tg-forwarder -f
   # Or if using screen:
   screen -r bots
   ```

---

## 🔍 Troubleshooting

**Bot won't start:**
- Check that all environment variables are set
- Verify `BOT_TOKEN` is correct
- Check logs for specific error messages

**Webhook not receiving messages:**
- Verify `WEBHOOK_URL` is correct and accessible
- Check if webhook requires HTTPS (set `ALLOW_INSECURE_WEBHOOK=true` only for testing)
- Look at bot logs to see webhook response status

**Session file issues:**
- Make sure `user_forwarder.session` is in the same directory as `user_forwarder.py`
- If missing, run `user_forwarder.py` once to generate it (you'll need to login)

**Permission denied:**
- Make sure session file is readable: `chmod 600 user_forwarder.session`

---

## 📝 Quick Reference

**Start bots:** `python run_bots.py`

**Stop bots:** Press `Ctrl+C` or `systemctl stop tg-forwarder`

**View logs:** Check DigitalOcean logs (App Platform) or `journalctl -u tg-forwarder` (Droplet)

**Update code:** Pull latest changes and restart the service

---

## 🛡️ Security Best Practices

1. ✅ **Never commit `.env` or `.session` files** (`.gitignore` handles this)
2. ✅ **Use HTTPS webhooks only** (don't set `ALLOW_INSECURE_WEBHOOK=true` in production)
3. ✅ **Set `WEBHOOK_SHARED_SECRET`** if your webhook is public
4. ✅ **Restrict `APPROVER_IDS`** to trusted users only
5. ✅ **Use `ALLOWED_CHAT_IDS`** to limit which chats the bot processes
6. ✅ **Keep logs at INFO level** in production (DEBUG may leak sensitive data)

---

## 💡 Need Help?

- Check the logs first - they usually tell you what's wrong
- Verify all environment variables are set correctly
- Make sure your webhook URL is accessible and returns 200 OK
- Test locally before deploying to catch issues early

