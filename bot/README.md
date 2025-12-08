# Freya Trades Telegram Bot

This bot watches a Telegram channel for trading signals and forwards them to the website.

## Setup

### 1. Create a Telegram Bot

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts
3. Copy the bot token

### 2. Add Bot to Source Channel

1. Add your bot as an admin to the source channel
2. Give it permission to read messages
3. Get the channel ID (use [@userinfobot](https://t.me/userinfobot))

### 3. Configure Environment

Create a `.env` file in this folder:

```env
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_SOURCE_CHANNEL_ID=-1001234567890
WEBSITE_API_URL=http://localhost:3000
INGEST_API_KEY=your-secret-key
```

### 4. Install & Run

```bash
cd bot
npm install
npm start
```

## Message Formats

The bot recognizes and forwards these message types:

### New Signal
```
script          : BTCUSD
Position        : BUY
Enter Price     : 90827.56
Take Profit 1   : 91528.57
Take Profit 2   : 91995.90
Take Profit 3   : 92696.91
Take Profit 4   : 93631.58
Stoploss        : 89659.22
```

### Take Profit Update
```
Position Status
Take Profit 3 From Long Signal
at Price : 25822.02 in NAS100
```

### Stop Loss Hit
```
Position Status
Hit SL From Long Signal
Price : 4249.13 in XAUUSD
```

## Commands

- `/start` - Show bot info
- `/stats` - Show message statistics
- `/test` - Send a test signal

## Filtering Rules

The bot IGNORES:
- Messages without the signal format
- Media (images, videos, documents)
- Links
- Random text messages
- "WAZIR FOREX ALGO" headers (removed before forwarding)
- "Any inquiries Dm @..." footers (removed before forwarding)

## Production Deployment

For 24/7 operation, use PM2:

```bash
npm install -g pm2
pm2 start telegram-bot.ts --interpreter ts-node
pm2 save
pm2 startup
```

