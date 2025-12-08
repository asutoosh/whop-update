/**
 * Telegram Bot Service
 * Watches source channel and forwards parsed signals to the website API
 * 
 * Run with: npx ts-node bot/telegram-bot.ts
 * Or build and run: npm run bot
 */

import { Telegraf, Context } from 'telegraf'
import { message } from 'telegraf/filters'

// Configuration from environment
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || ''
const SOURCE_CHANNEL_ID = process.env.TELEGRAM_SOURCE_CHANNEL_ID || ''
const WEBSITE_API_URL = process.env.WEBSITE_API_URL || 'http://localhost:3000'
const INGEST_API_KEY = process.env.INGEST_API_KEY || 'your-secret-key'

// Validate configuration
if (!BOT_TOKEN) {
  console.error('❌ TELEGRAM_BOT_TOKEN is required')
  process.exit(1)
}

// Create bot instance
const bot = new Telegraf(BOT_TOKEN)

// Statistics
let messagesReceived = 0
let messagesForwarded = 0
let messagesIgnored = 0

/**
 * Check if message matches signal format
 */
function isValidSignalMessage(text: string): boolean {
  // Check for new signal format
  const isNewSignal = 
    /script\s*:\s*\w+/i.test(text) &&
    /position\s*:\s*(BUY|SELL)/i.test(text) &&
    /enter\s*price\s*:\s*[\d.]+/i.test(text) &&
    /take\s*profit\s*1\s*:\s*[\d.]+/i.test(text) &&
    /stoploss\s*:\s*[\d.]+/i.test(text)

  // Check for TP update format
  const isTpUpdate = 
    /take\s*profit\s*\d+\s*from\s*(long|short)\s*signal/i.test(text) &&
    /(?:at\s*)?price\s*:\s*[\d.]+\s*in\s*\w+/i.test(text)

  // Check for SL hit format
  const isSlHit = 
    /hit\s*sl\s*from\s*(long|short)\s*signal/i.test(text) &&
    /price\s*:\s*[\d.]+\s*in\s*\w+/i.test(text)

  return isNewSignal || isTpUpdate || isSlHit
}

/**
 * Forward message to website API
 */
async function forwardToWebsite(text: string): Promise<boolean> {
  try {
    const response = await fetch(`${WEBSITE_API_URL}/api/signals/ingest`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${INGEST_API_KEY}`,
      },
      body: JSON.stringify({ message: text }),
    })

    const data = await response.json()
    
    if (data.status === 'success') {
      console.log(`✅ Signal forwarded: ${data.signal?.script || 'Update'}`)
      return true
    } else if (data.status === 'ignored') {
      console.log(`⏭️ Message ignored by parser`)
      return false
    } else {
      console.error('❌ API error:', data)
      return false
    }
  } catch (error) {
    console.error('❌ Failed to forward message:', error)
    return false
  }
}

/**
 * Process incoming message
 */
async function processMessage(ctx: Context, text: string) {
  messagesReceived++
  
  // Skip if not valid signal format
  if (!isValidSignalMessage(text)) {
    messagesIgnored++
    console.log(`⏭️ Ignored non-signal message (${messagesIgnored} total ignored)`)
    return
  }

  // Forward to website
  const success = await forwardToWebsite(text)
  if (success) {
    messagesForwarded++
  }

  // Log stats every 10 messages
  if (messagesReceived % 10 === 0) {
    console.log(`\n📊 Stats: ${messagesReceived} received, ${messagesForwarded} forwarded, ${messagesIgnored} ignored\n`)
  }
}

// Handle channel posts
bot.on(message('text'), async (ctx) => {
  const text = ctx.message.text
  
  // Check if from source channel (if configured)
  if (SOURCE_CHANNEL_ID) {
    const chatId = ctx.chat.id.toString()
    if (chatId !== SOURCE_CHANNEL_ID && chatId !== SOURCE_CHANNEL_ID.replace('-100', '-')) {
      // Not from source channel, check if it's a forwarded message
      const forwardFrom = (ctx.message as any).forward_from_chat
      if (!forwardFrom || forwardFrom.id.toString() !== SOURCE_CHANNEL_ID.replace('-100', '')) {
        return // Ignore messages not from source channel
      }
    }
  }

  await processMessage(ctx, text)
})

// Handle forwarded messages (when bot receives forwarded posts)
bot.on(message('forward_date'), async (ctx) => {
  const text = (ctx.message as any).text
  if (text) {
    await processMessage(ctx, text)
  }
})

// Start command
bot.command('start', (ctx) => {
  ctx.reply(`🤖 Freya Trades Signal Bot

I forward trading signals from the source channel to the website.

📊 Current Stats:
- Messages received: ${messagesReceived}
- Signals forwarded: ${messagesForwarded}
- Messages ignored: ${messagesIgnored}

Use /stats to see current statistics.`)
})

// Stats command
bot.command('stats', (ctx) => {
  ctx.reply(`📊 Bot Statistics

Messages received: ${messagesReceived}
Signals forwarded: ${messagesForwarded}
Messages ignored: ${messagesIgnored}

Forwarding to: ${WEBSITE_API_URL}`)
})

// Test command - manually test a message
bot.command('test', async (ctx) => {
  const testMessage = `script          : BTCUSD
Position        : BUY
Enter Price     : 90827.56
Take Profit 1   : 91528.57
Take Profit 2   : 91995.90
Take Profit 3   : 92696.91
Take Profit 4   : 93631.58
Stoploss        : 89659.22`

  ctx.reply('🧪 Testing with sample signal...')
  const success = await forwardToWebsite(testMessage)
  ctx.reply(success ? '✅ Test signal forwarded!' : '❌ Test failed')
})

// Error handling
bot.catch((err, ctx) => {
  console.error('Bot error:', err)
})

// Graceful shutdown
process.once('SIGINT', () => {
  console.log('\n👋 Shutting down bot...')
  bot.stop('SIGINT')
})

process.once('SIGTERM', () => {
  console.log('\n👋 Shutting down bot...')
  bot.stop('SIGTERM')
})

// Start bot
console.log('🚀 Starting Freya Trades Signal Bot...')
console.log(`📡 API URL: ${WEBSITE_API_URL}`)
console.log(`📺 Source Channel: ${SOURCE_CHANNEL_ID || 'Any channel (not restricted)'}`)

bot.launch()
  .then(() => {
    console.log('✅ Bot is running!')
    console.log('\n💡 The bot will now forward valid signals to the website.')
    console.log('   Valid formats:')
    console.log('   - New signals (script, position, entry, TPs, SL)')
    console.log('   - Take Profit updates')
    console.log('   - Stop Loss hits\n')
  })
  .catch((err) => {
    console.error('❌ Failed to start bot:', err)
    process.exit(1)
  })

