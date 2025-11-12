# Step-by-Step Droplet Setup Guide

Follow these steps to deploy your Telegram bots on your DigitalOcean droplet.

---

## 📋 Prerequisites

Before starting, make sure you have:
- ✅ Your droplet IP address
- ✅ Your SSH key or root password
- ✅ Your `.env` file ready (or the values from `env.example`)
- ✅ Your `user_forwarder.session` file

---

## Step 1: Connect to Your Droplet

### On Windows (PowerShell):

**Option A: Using SSH Key (Recommended)**
```powershell
ssh root@YOUR_DROPLET_IP
```

**Option B: Using Password**
```powershell
ssh root@YOUR_DROPLET_IP
# Enter your root password when prompted
```

**Replace `YOUR_DROPLET_IP` with your actual droplet IP address.**

You should see something like:
```
Welcome to Ubuntu 22.04 LTS
root@your-droplet:~#
```

---

## Step 2: Update System and Install Python

Once connected, run these commands:

```bash
# Update system packages
apt update && apt upgrade -y

# Install Python 3 and pip
apt install -y python3 python3-pip git

# Verify installation
python3 --version
pip3 --version
```

You should see Python 3.10+ and pip versions.

---

## Step 3: Clone Your Repository

```bash
# Navigate to home directory
cd ~

# Clone your GitHub repository
git clone git@github.com:asutoosh/whop-update.git

# If SSH key isn't set up, use HTTPS instead:
# git clone https://github.com/asutoosh/whop-update.git

# Navigate into the project
cd whop-update
```

---

## Step 4: Install Python Dependencies

**Important:** Ubuntu 22.04+ uses an "externally-managed-environment" for Python. We'll use a virtual environment (recommended) or install system-wide.

### Option A: Virtual Environment (Recommended)

```bash
# Install python3-venv if not already installed
apt install -y python3-venv

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

**Note:** You'll need to activate the virtual environment each time you run the bots:
```bash
source venv/bin/activate
python3 run_bots.py
```

### Option B: Install System-Wide (Simpler for systemd)

```bash
# Install required packages system-wide (bypasses protection)
pip3 install -r requirements.txt --break-system-packages
```

This will install:
- python-telegram-bot
- telethon
- requests
- python-dotenv

---

## Step 5: Set Up Environment Variables

### Option A: Create .env File (Recommended)

```bash
# Create .env file
nano .env
```

**Paste your environment variables** (copy from your local `.env` or use `env.example` as template):

```
BOT_TOKEN=your_bot_token_here
API_ID=12345678
API_HASH=your_api_hash_here
SOURCE_CHANNEL=@wazirforexalerts
FORWARD_TO_CHAT_ID=-1001234567890
FORWARD_TO_THREAD_ID=7
WEBHOOK_URL=https://your-webhook-url.com/endpoint
APPROVER_IDS=123456789
LOG_LEVEL=INFO
USERBOT_LOG_LEVEL=INFO
```

**To save in nano:**
- Press `Ctrl + X`
- Press `Y` to confirm
- Press `Enter` to save

**To verify:**
```bash
cat .env
```

---

## Step 6: Upload Session File

You need to upload your `user_forwarder.session` file from your local machine to the droplet.

### On Windows (PowerShell - from your local machine):

```powershell
# Navigate to your local project directory
cd "F:\whop\tg forward"

# Upload session file using SCP
scp user_forwarder.session root@YOUR_DROPLET_IP:/root/whop-update/
```

**Replace `YOUR_DROPLET_IP` with your actual droplet IP.**

**If it asks for password, enter your droplet root password.**

**Verify on droplet:**
```bash
ls -la user_forwarder.session
```

You should see the file listed.

---

## Step 7: Test the Bots Manually

Before setting up auto-start, let's test if everything works:

```bash
# Test the bots (this will run in foreground)
python3 run_bots.py
```

**What to expect:**
- You should see logs from both bots
- The userbot might ask you to login (if session file is missing/invalid)
- Check for any errors

**To stop:** Press `Ctrl + C`

**If you see errors:**
- Check that all environment variables are set correctly
- Verify the session file is in the right place
- Check the error messages for clues

---

## Step 8: Set Up Auto-Start with systemd

This will make your bots start automatically on server reboot and restart if they crash.

### Create Service File

```bash
# Create systemd service file
nano /etc/systemd/system/tg-forwarder.service
```

**Paste this content:**

**If you used Option A (Virtual Environment):**
```ini
[Unit]
Description=Telegram Forwarder Bots
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/whop-update
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/root/whop-update/venv/bin/python /root/whop-update/run_bots.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**If you used Option B (System-Wide Installation):**
```ini
[Unit]
Description=Telegram Forwarder Bots
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/whop-update
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /root/whop-update/run_bots.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Save:** `Ctrl + X`, then `Y`, then `Enter`

### Enable and Start Service

```bash
# Reload systemd to recognize new service
systemctl daemon-reload

# Enable service to start on boot
systemctl enable tg-forwarder

# Start the service
systemctl start tg-forwarder

# Check status
systemctl status tg-forwarder
```

**You should see:**
```
● tg-forwarder.service - Telegram Forwarder Bots
     Loaded: loaded (/etc/systemd/system/tg-forwarder.service; enabled)
     Active: active (running) since...
```

---

## Step 9: Monitor Your Bots

### View Logs

```bash
# View live logs
journalctl -u tg-forwarder -f

# View last 100 lines
journalctl -u tg-forwarder -n 100

# View logs from today
journalctl -u tg-forwarder --since today
```

**To exit log viewer:** Press `Ctrl + C`

### Check Status

```bash
# Check if service is running
systemctl status tg-forwarder

# Restart service (if needed)
systemctl restart tg-forwarder

# Stop service
systemctl stop tg-forwarder

# Start service
systemctl start tg-forwarder
```

---

## Step 10: Verify Everything Works

1. **Check bots are running:**
   ```bash
   systemctl status tg-forwarder
   ```

2. **Check logs for errors:**
   ```bash
   journalctl -u tg-forwarder -n 50
   ```

3. **Test by sending a message:**
   - Send a test message to your monitored channel
   - Check logs to see if it's being processed
   - Verify webhook is receiving messages

---

## 🔧 Troubleshooting

### Bot Won't Start

**Check logs:**
```bash
journalctl -u tg-forwarder -n 100
```

**Common issues:**
- Missing environment variables → Check `.env` file
- Wrong paths → Verify `WorkingDirectory` in service file
- Python not found → Check `ExecStart` path: `which python3`
- Session file missing → Upload `user_forwarder.session`

### Session File Issues

**If userbot asks for login:**
```bash
# Stop the service
systemctl stop tg-forwarder

# Run userbot manually to login
cd /root/whop-update
python3 user_forwarder.py

# Follow login prompts (Telegram will send code)
# After login, press Ctrl+C

# Restart service
systemctl start tg-forwarder
```

### Permission Issues

```bash
# Make sure files are readable
chmod 644 /root/whop-update/*.py
chmod 600 /root/whop-update/user_forwarder.session
chmod 644 /root/whop-update/.env
```

### Update Code

```bash
# Stop service
systemctl stop tg-forwarder

# Pull latest code
cd /root/whop-update
git pull

# Install new dependencies (if any)
pip3 install -r requirements.txt

# Restart service
systemctl start tg-forwarder
```

---

## 📝 Quick Reference Commands

```bash
# View logs
journalctl -u tg-forwarder -f

# Check status
systemctl status tg-forwarder

# Restart bots
systemctl restart tg-forwarder

# Stop bots
systemctl stop tg-forwarder

# Start bots
systemctl start tg-forwarder

# View last 50 log lines
journalctl -u tg-forwarder -n 50
```

---

## ✅ Success Checklist

- [ ] Connected to droplet via SSH
- [ ] Installed Python and dependencies
- [ ] Cloned repository
- [ ] Created `.env` file with all variables
- [ ] Uploaded `user_forwarder.session` file
- [ ] Tested bots manually (they run without errors)
- [ ] Created systemd service file
- [ ] Enabled and started service
- [ ] Verified bots are running (`systemctl status`)
- [ ] Checked logs (no errors)
- [ ] Tested with actual message (webhook receives data)

---

## 🎉 You're Done!

Your bots should now be running 24/7 on your DigitalOcean droplet!

**Next steps:**
- Monitor logs regularly to ensure everything works
- Set up log rotation if logs get too large
- Consider setting up monitoring/alerts
- Backup your session file regularly

**Need help?** Check the logs first - they usually tell you what's wrong!

