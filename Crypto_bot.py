import os
import requests
import asyncio
import nest_asyncio
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

nest_asyncio.apply()

BOT_TOKEN = os.getenv("8047872044:AAGhaUBqIGMRB4SGHbVzFpqEyTUk_I1bJMk")  # Use environment variable

coin_map = {}
alerts = {}  # Dictionary to store user alerts: {chat_id: [(coin_id, target_price), ...]}

def load_coin_list():
    global coin_map
    url = "https://api.coingecko.com/api/v3/coins/list"
    try:
        data = requests.get(url).json()
        coin_map = {coin["symbol"].lower(): coin["id"] for coin in data}
    except Exception as e:
        print("Error loading coin list:", e)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to CryptoBot!*\n\n"
        "Here are some things I can do:\n\n"
        "💰 `/price <coin>` - Get live prices (INR, USD, EUR, GBP)\n"
        "📈 `/convert <amount> <coin1> <coin2>` - Convert between two coins\n"
        "📊 `/trending` - Show trending coins\n"
        "🔔 `/alert <coin> <price>` - Set a price alert\n"
        "ℹ️ `/help` - List all commands\n\n"
        "Example:\n"
        "`/price btc`\n"
        "`/alert eth 250000`\n"
        "`/convert 1 btc eth`\n\n"
        "_Stay updated with real-time crypto data!_", parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Usage: /price <coin>\nExample: /price btc")
        return

    coin_input = context.args[0].lower()
    coin_id = coin_map.get(coin_input)
    if not coin_id:
        await update.message.reply_text("❌ Coin not found.")
        return

    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=inr,usd,eur,gbp"
    data = requests.get(url).json()

    if coin_id in data:
        prices = data[coin_id]
        await update.message.reply_text(
            f"💰 *{coin_input.upper()} Price:*\n"
            f"🇮🇳 INR: ₹{prices['inr']:,}\n"
            f"🇺🇸 USD: ${prices['usd']:,}\n"
            f"🇪🇺 EUR: €{prices['eur']:,}\n"
            f"🇬🇧 GBP: £{prices['gbp']:,}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Could not fetch price.")

async def convert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("Usage: /convert <amount> <coin1> <coin2>")
        return

    try:
        amount = float(context.args[0])
        coin1 = context.args[1].lower()
        coin2 = context.args[2].lower()
        id1 = coin_map.get(coin1)
        id2 = coin_map.get(coin2)

        if not id1 or not id2:
            await update.message.reply_text("❌ One or both coins not found.")
            return

        url = f"https://api.coingecko.com/api/v3/simple/price?ids={id1},{id2}&vs_currencies=usd"
        data = requests.get(url).json()
        usd1 = data[id1]["usd"]
        usd2 = data[id2]["usd"]
        result = (amount * usd1) / usd2

        await update.message.reply_text(
            f"🔄 *{amount} {coin1.upper()}* ≈ *{result:.6f} {coin2.upper()}*", parse_mode="Markdown"
        )
    except Exception:
        await update.message.reply_text("⚠️ Conversion failed. Please check the input.")

async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = "https://api.coingecko.com/api/v3/search/trending"
    data = requests.get(url).json()

    message = "🔥 *Top Trending Coins:*\n"
    for i, coin in enumerate(data["coins"], start=1):
        item = coin["item"]
        message += f"{i}. {item['name']} ({item['symbol'].upper()})\n"

    await update.message.reply_text(message, parse_mode="Markdown")

async def alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /alert <coin> <price>")
        return

    coin_input = context.args[0].lower()
    try:
        target_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid price.")
        return

    coin_id = coin_map.get(coin_input)
    if not coin_id:
        await update.message.reply_text("❌ Coin not found.")
        return

    chat_id = update.message.chat_id
    alerts.setdefault(chat_id, []).append((coin_id, coin_input.upper(), target_price))
    await update.message.reply_text(f"🔔 Alert set for {coin_input.upper()} at ₹{target_price:,}!")

async def check_alerts(app):
    while True:
        for chat_id, user_alerts in list(alerts.items()):
            for coin_id, symbol, target in user_alerts:
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=inr"
                data = requests.get(url).json()
                current_price = data[coin_id]["inr"]

                if current_price >= target:
                    app.bot.send_message(
                        chat_id=chat_id,
                        text=f"📢 {symbol} reached ₹{current_price:,}!\n(Target: ₹{target:,})"
                    )
                    user_alerts.remove((coin_id, symbol, target))
        await asyncio.sleep(60)

async def post_init(application):
    await application.bot.set_my_commands([
        BotCommand("start", "Start the bot"),
        BotCommand("price", "Get live price of a coin"),
        BotCommand("convert", "Convert coin1 to coin2"),
        BotCommand("trending", "Show trending coins"),
        BotCommand("alert", "Set a price alert"),
        BotCommand("help", "List available commands"),
    ])
    asyncio.create_task(check_alerts(application))

async def main():
    load_coin_list()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("convert", convert))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("alert", alert))

    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
