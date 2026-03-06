"""
MEXC Telegram Trade Bot Şablonu
"""

import os
import logging
from dotenv import load_dotenv
import ccxt
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

load_dotenv()

TELEGRAM_TOKEN  = os.getenv("TELEGRAM_TOKEN")
MEXC_API_KEY    = os.getenv("MEXC_API_KEY")
MEXC_SECRET_KEY = os.getenv("MEXC_SECRET_KEY")
ALLOWED_USER_ID = int(os.getenv("ALLOWED_USER_ID", "0"))

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
log = logging.getLogger(__name__)

exchange = ccxt.mexc({
    "apiKey": MEXC_API_KEY,
    "secret": MEXC_SECRET_KEY,
    "enableRateLimit": True,
})

def is_authorized(update): return update.effective_user.id == ALLOWED_USER_ID
def get_price(symbol): return exchange.fetch_ticker(symbol)["last"]
def get_balance():
    b = exchange.fetch_balance()
    return {"USDT": b["free"].get("USDT",0), "BTC": b["free"].get("BTC",0), "ETH": b["free"].get("ETH",0)}
def place_market_order(symbol, side, amount): return exchange.create_market_order(symbol, side, amount)

async def start(update, ctx):
    if not is_authorized(update): await update.message.reply_text("⛔ İcazəniz yoxdur."); return
    keyboard = [
        [InlineKeyboardButton("💰 Balans", callback_data="balance"), InlineKeyboardButton("📈 Qiymət", callback_data="price_menu")],
        [InlineKeyboardButton("🟢 BUY", callback_data="buy_menu"), InlineKeyboardButton("🔴 SELL", callback_data="sell_menu")],
        [InlineKeyboardButton("📋 Açıq Orderlər", callback_data="open_orders")],
    ]
    await update.message.reply_text("👋 MEXC Trade Botuna xoş gəldiniz!", reply_markup=InlineKeyboardMarkup(keyboard))

async def cmd_balance(update, ctx):
    if not is_authorized(update): return
    bal = get_balance()
    await update.message.reply_text(f"💼 *Balans:*\n  USDT: `{bal['USDT']:.2f}`\n  BTC: `{bal['BTC']:.6f}`\n  ETH: `{bal['ETH']:.6f}`", parse_mode="Markdown")

async def cmd_price(update, ctx):
    if not is_authorized(update): return
    if not ctx.args: await update.message.reply_text("İstifadə: /price BTC/USDT"); return
    try:
        price = get_price(ctx.args[0].upper())
        await update.message.reply_text(f"💹 *{ctx.args[0].upper()}* = `{price}` USDT", parse_mode="Markdown")
    except Exception as e: await update.message.reply_text(f"❌ Xəta: {e}")

async def cmd_buy(update, ctx):
    if not is_authorized(update): return
    if len(ctx.args) < 2: await update.message.reply_text("İstifadə: /buy BTC/USDT 0.001"); return
    try:
        order = place_market_order(ctx.args[0].upper(), "buy", float(ctx.args[1]))
        await update.message.reply_text(f"✅ *BUY verildi!*\nOrder ID: `{order['id']}`", parse_mode="Markdown")
    except Exception as e: await update.message.reply_text(f"❌ Xəta: {e}")

async def cmd_sell(update, ctx):
    if not is_authorized(update): return
    if len(ctx.args) < 2: await update.message.reply_text("İstifadə: /sell BTC/USDT 0.001"); return
    try:
        order = place_market_order(ctx.args[0].upper(), "sell", float(ctx.args[1]))
        await update.message.reply_text(f"✅ *SELL verildi!*\nOrder ID: `{order['id']}`", parse_mode="Markdown")
    except Exception as e: await update.message.reply_text(f"❌ Xəta: {e}")

async def cmd_orders(update, ctx):
    if not is_authorized(update): return
    symbol = ctx.args[0].upper() if ctx.args else "BTC/USDT"
    try:
        orders = exchange.fetch_open_orders(symbol)
        if not orders: await update.message.reply_text(f"📭 {symbol} üzrə açıq order yoxdur."); return
        lines = [f"📋 *Açıq Orderlər:*"]
        for o in orders: lines.append(f"• `{o['id']}` | {o['side'].upper()} | `{o['price']}` | `{o['amount']}`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
    except Exception as e: await update.message.reply_text(f"❌ Xəta: {e}")

async def button_handler(update, ctx):
    query = update.callback_query
    await query.answer()
    if query.data == "balance":
        bal = get_balance()
        await query.edit_message_text(f"💼 *Balans:*\n  USDT: `{bal['USDT']:.2f}`\n  BTC: `{bal['BTC']:.6f}`", parse_mode="Markdown")
    elif query.data == "price_menu": await query.edit_message_text("Qiymət: `/price BTC/USDT`", parse_mode="Markdown")
    elif query.data == "buy_menu": await query.edit_message_text("BUY: `/buy BTC/USDT 0.001`", parse_mode="Markdown")
    elif query.data == "sell_menu": await query.edit_message_text("SELL: `/sell BTC/USDT 0.001`", parse_mode="Markdown")
    elif query.data == "open_orders": await query.edit_message_text("Orderlər: `/orders BTC/USDT`", parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",   start))
    app.add_handler(CommandHandler("balance", cmd_balance))
    app.add_handler(CommandHandler("price",   cmd_price))
    app.add_handler(CommandHandler("buy",     cmd_buy))
    app.add_handler(CommandHandler("sell",    cmd_sell))
    app.add_handler(CommandHandler("orders",  cmd_orders))
    app.add_handler(CallbackQueryHandler(button_handler))
    log.info("Bot işə düşdü...")
    app.run_polling()

if __name__ == "__main__":
    main()
