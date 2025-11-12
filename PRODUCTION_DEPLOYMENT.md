# Production Deployment Guide

This guide will set up your bots to run automatically in production with systemd.

---

## Step 1: Stop Manual Process

If you're currently running `python3 run_bots.py` manually:

1. **Press `Ctrl + C`** in the terminal where it's running
2. Make sure it's fully stopped

---

## Step 2: Determine Your Python Setup

Check if you're using a virtual environment:

```bash
cd ~/whop-update

# Check if venv exists
ls -la venv/
```

- **If `venv/` folder exists** → You're using virtual environment (Option A)
- **If no `venv/` folder** → You're using system-wide Python (Option B)

---

## Step 3: Create systemd Service File

```bash
nano /etc/systemd/system/tg-forwarder.service
```

### If Using Virtual Environment (Option A):

Paste this:

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

### If Using System-Wide Python (Option B):

Paste this:

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

---

## Step 4: Enable and Start the Service

```bash
# Reload systemd to recognize the new service
systemctl daemon-reload

# Enable service to start automatically on boot
systemctl enable tg-forwarder

# Start the service now
systemctl start tg-forwarder

# Check if it's running
systemctl status tg-forwarder
```

**You should see:**
```
● tg-forwarder.service - Telegram Forwarder Bots
     Loaded: loaded (/etc/systemd/system/tg-forwarder.service; enabled)
     Active: active (running) since...
```

---

## Step 5: Verify It's Working

### Check Status:
```bash
systemctl status tg-forwarder
```

### View Live Logs:
```bash
journalctl -u tg-forwarder -f
```

You should see:
- `INFO:launcher:Starting both bots...`
- `INFO:forwarder_bot:Bot started. Waiting for forwarded messages...`
- `INFO:user_forwarder:Listening as user session...`

### Test the Bots:
1. Send a test message to your monitored channel
2. Check logs to see if it's being processed
3. Try clicking Allow/Deny buttons - they should work

---

## Step 6: Useful Commands

### View Logs:
```bash
# Live logs (follow mode)
journalctl -u tg-forwarder -f

# Last 100 lines
journalctl -u tg-forwarder -n 100

# Logs from today
journalctl -u tg-forwarder --since today

# Logs with timestamps
journalctl -u tg-forwarder -f --no-pager
```

### Control the Service:
```bash
# Start
systemctl start tg-forwarder

# Stop
systemctl stop tg-forwarder

# Restart
systemctl restart tg-forwarder

# Check status
systemctl status tg-forwarder

# Disable auto-start on boot
systemctl disable tg-forwarder

# Enable auto-start on boot
systemctl enable tg-forwarder
```

---

## Step 7: Auto-Restart on Failure

The service is already configured with:
- `Restart=always` - Restarts if it crashes
- `RestartSec=10` - Waits 10 seconds before restarting

**This means:**
- ✅ Bots restart automatically if they crash
- ✅ Bots start automatically when server reboots
- ✅ Bots restart if they exit for any reason

---

## Troubleshooting

### Service Won't Start

**Check logs:**
```bash
journalctl -u tg-forwarder -n 50
```

**Common issues:**
- Wrong Python path → Check `ExecStart` path in service file
- Missing dependencies → Run `pip install -r requirements.txt`
- Wrong working directory → Check `WorkingDirectory` in service file

### Service Keeps Restarting

**Check why it's crashing:**
```bash
journalctl -u tg-forwarder -n 100
```

Look for error messages and fix them.

### Bots Not Receiving Messages

**Check if both bots are running:**
```bash
systemctl status tg-forwarder
journalctl -u tg-forwarder -f
```

You should see logs from both `forwarder_bot` and `user_forwarder`.

---

## Production Checklist

- [ ] Service file created at `/etc/systemd/system/tg-forwarder.service`
- [ ] Service enabled (`systemctl enable tg-forwarder`)
- [ ] Service started (`systemctl start tg-forwarder`)
- [ ] Status shows "active (running)"
- [ ] Logs show both bots started successfully
- [ ] Test message processed correctly
- [ ] Allow/Deny buttons work
- [ ] Service restarts automatically on crash (test by killing process)
- [ ] Service starts on server reboot (test by rebooting)

---

## Update Code in Production

When you need to update the code:

```bash
cd ~/whop-update

# Pull latest code
git pull

# Install new dependencies (if any)
source venv/bin/activate  # if using venv
pip install -r requirements.txt

# Restart service
systemctl restart tg-forwarder

# Check it's running
systemctl status tg-forwarder
```

---

## Update .env File After Deployment

**Important:** After changing any values in `.env`, you **must restart the service** for changes to take effect!

### Steps:

1. **Edit your `.env` file:**
   ```bash
   cd ~/whop-update
   nano .env
   ```
   
   Make your changes (e.g., update `APPROVAL_CHAT_ID`, `WEBHOOK_URL`, etc.)

2. **Save the file:**
   - `Ctrl + X`, then `Y`, then `Enter`

3. **Restart the service:**
   ```bash
   systemctl restart tg-forwarder
   ```

4. **Verify it's running:**
   ```bash
   systemctl status tg-forwarder
   ```

5. **Check logs to confirm:**
   ```bash
   journalctl -u tg-forwarder -f
   ```

### Common .env Changes:

- **Changing `APPROVAL_CHAT_ID`** → Restart required
- **Changing `WEBHOOK_URL`** → Restart required
- **Changing `APPROVER_IDS`** → Restart required
- **Changing `LOG_LEVEL`** → Restart required
- **Any environment variable** → Restart required

**Note:** The service reads `.env` file only when it starts, so changes won't take effect until you restart!

---

## Monitor in Production

### Set Up Log Rotation (Optional but Recommended)

Create log rotation config:

```bash
nano /etc/logrotate.d/tg-forwarder
```

Paste:
```
/var/log/tg-forwarder.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

### Monitor Service Health

You can set up monitoring to alert you if the service stops:

```bash
# Check if service is running (returns 0 if running)
systemctl is-active tg-forwarder

# Use in monitoring scripts
if ! systemctl is-active --quiet tg-forwarder; then
    echo "Service is down!"
    systemctl restart tg-forwarder
fi
```

---

## ✅ You're Done!

Your bots are now running in production with:
- ✅ Automatic startup on boot
- ✅ Automatic restart on crash
- ✅ Logging to systemd journal
- ✅ Easy management with systemctl commands

No more need to run `python3 run_bots.py` manually!

