# “””
MEXC Telegram Advanced Spot Trade Bot

Funksiyalar:

- Yalnız SPOT əməliyyatlar
- PAXG/USDT dəstəyi
- Watchlist (öz coinlərinizi əlavə edin)
- Market / Limit order
- Stop-Loss / Take-Profit (avtomatik izləmə)
- Qiymət alerti
- Texniki analiz: dəstək/müqavimət, trend xətləri
- Al/Sat siqnalları (EMA, RSI, MACD)

Tələblər:
pip install python-telegram-bot ccxt pandas numpy python-dotenv
“””

import os
import asyncio
import logging
from dotenv import load_dotenv

import ccxt
import pandas as pd
import numpy as np

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
ApplicationBuilder, CommandHandler, CallbackQueryHandler,
ContextTypes,
)

# ── Konfiqurasiya ──────────────────────────────────────────────────────────────

load_dotenv()

TELEGRAM_TOKEN  = os.getenv(“TELEGRAM_TOKEN”)
MEXC_API_KEY    = os.getenv(“MEXC_API_KEY”)
MEXC_SECRET_KEY = os.getenv(“MEXC_SECRET_KEY”)
ALLOWED_USER_ID = int(os.getenv(“ALLOWED_USER_ID”, “0”))

logging.basicConfig(format=”%(asctime)s | %(levelname)s | %(message)s”, level=logging.INFO)
log = logging.getLogger(**name**)

# ── MEXC Bağlantısı (yalnız SPOT) ─────────────────────────────────────────────

exchange = ccxt.mexc({
“apiKey”: MEXC_API_KEY,
“secret”: MEXC_SECRET_KEY,
“enableRateLimit”: True,
“options”: {“defaultType”: “spot”},
})

# ── Yaddaş ────────────────────────────────────────────────────────────────────

price_alerts = {}   # {symbol: {“above”: float, “below”: float}}
sl_tp_orders = {}   # {symbol: {“buy_price”: float, “sl”: float, “tp”: float, “amount”: float}}
watchlist    = []   # İstifadəçinin coin siyahısı

DEFAULT_COINS = [
“BTC/USDT”, “ETH/USDT”, “SOL/USDT”, “XRP/USDT”,
“DOGE/USDT”, “SLVON/USDT”, “NVDAON/USDT”,
“GOLD(PAXG)/USDT”, “USOON/USDT”
]

# ══════════════════════════════════════════════════════════════════════════════

# KÖMƏKÇİ FUNKSİYALAR

# ══════════════════════════════════════════════════════════════════════════════

def is_authorized(update: Update) -> bool:
return update.effective_user.id == ALLOWED_USER_ID

def get_price(symbol: str) -> float:
return exchange.fetch_ticker(symbol)[“last”]

def get_balance() -> dict:
bal = exchange.fetch_balance()
result = {“USDT”: round(bal[“free”].get(“USDT”, 0), 4)}
for coin in [“BTC”, “ETH”, “SOL”, “XRP”, “DOGE”, “PAXG”, “BNB”, “PEPE”, “AVAX”, “ADA”]:
free = bal[“free”].get(coin, 0)
if free > 0:
result[coin] = round(free, 8)
return result

def get_ohlcv(symbol: str, timeframe: str = “1h”, limit: int = 100) -> pd.DataFrame:
ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
df = pd.DataFrame(ohlcv, columns=[“timestamp”, “open”, “high”, “low”, “close”, “volume”])
df[“timestamp”] = pd.to_datetime(df[“timestamp”], unit=“ms”)
return df

def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
df[“ema9”]  = df[“close”].ewm(span=9,  adjust=False).mean()
df[“ema21”] = df[“close”].ewm(span=21, adjust=False).mean()
df[“ema50”] = df[“close”].ewm(span=50, adjust=False).mean()
delta    = df[“close”].diff()
gain     = delta.clip(lower=0)
loss     = -delta.clip(upper=0)
avg_gain = gain.ewm(com=13, adjust=False).mean()
avg_loss = loss.ewm(com=13, adjust=False).mean()
rs       = avg_gain / avg_loss.replace(0, np.nan)
df[“rsi”]         = 100 - (100 / (1 + rs))
ema12             = df[“close”].ewm(span=12, adjust=False).mean()
ema26             = df[“close”].ewm(span=26, adjust=False).mean()
df[“macd”]        = ema12 - ema26
df[“macd_signal”] = df[“macd”].ewm(span=9, adjust=False).mean()
df[“macd_hist”]   = df[“macd”] - df[“macd_signal”]
return df

def calc_support_resistance(df: pd.DataFrame) -> dict:
recent = df.tail(50)
highs  = recent[“high”].values
lows   = recent[“low”].values
resistance_levels = [highs[i] for i in range(1, len(highs)-1) if highs[i] > highs[i-1] and highs[i] > highs[i+1]]
support_levels    = [lows[i]  for i in range(1, len(lows)-1)  if lows[i]  < lows[i-1]  and lows[i]  < lows[i+1]]
current_price = df[“close”].iloc[-1]
supports    = sorted([s for s in support_levels    if s < current_price], reverse=True)
resistances = sorted([r for r in resistance_levels if r > current_price])
return {
“support1”:    round(supports[0],    8) if len(supports)    > 0 else None,
“support2”:    round(supports[1],    8) if len(supports)    > 1 else None,
“resistance1”: round(resistances[0], 8) if len(resistances) > 0 else None,
“resistance2”: round(resistances[1], 8) if len(resistances) > 1 else None,
}

def detect_trend(df: pd.DataFrame) -> str:
last = df.iloc[-1]
if last[“ema9”] > last[“ema21”] > last[“ema50”]:
return “📈 YÜKSƏLƏN TREND”
elif last[“ema9”] < last[“ema21”] < last[“ema50”]:
return “📉 DÜŞƏN TREND”
else:
return “↔️ YANBAYAN”

def generate_signal(df: pd.DataFrame) -> dict:
df   = calc_indicators(df)
last = df.iloc[-1]
prev = df.iloc[-2]
signals = []
score   = 0

```
if prev["ema9"] <= prev["ema21"] and last["ema9"] > last["ema21"]:
    signals.append("✅ EMA9 EMA21-i yuxarı kəsdi → AL")
    score += 2
elif prev["ema9"] >= prev["ema21"] and last["ema9"] < last["ema21"]:
    signals.append("🔴 EMA9 EMA21-i aşağı kəsdi → SAT")
    score -= 2

if last["rsi"] < 30:
    signals.append(f"✅ RSI aşırı satılmış: {last['rsi']:.1f} → AL imkanı")
    score += 1
elif last["rsi"] > 70:
    signals.append(f"🔴 RSI aşırı alınmış: {last['rsi']:.1f} → SAT imkanı")
    score -= 1
else:
    signals.append(f"ℹ️ RSI neytral: {last['rsi']:.1f}")

if prev["macd_hist"] <= 0 and last["macd_hist"] > 0:
    signals.append("✅ MACD müsbət keçdi → AL")
    score += 1
elif prev["macd_hist"] >= 0 and last["macd_hist"] < 0:
    signals.append("🔴 MACD mənfi keçdi → SAT")
    score -= 1

if score >= 2:     decision = "🟢 GÜCLÜ AL"
elif score == 1:   decision = "🟡 ZƏİF AL"
elif score == -1:  decision = "🟡 ZƏİF SAT"
elif score <= -2:  decision = "🔴 GÜCLÜ SAT"
else:              decision = "⚪ NEYTRAL"

return {
    "decision": decision,
    "trend":    detect_trend(df),
    "signals":  signals,
    "rsi":      round(last["rsi"], 1),
    "ema9":     round(last["ema9"],  6),
    "ema21":    round(last["ema21"], 6),
    "sr":       calc_support_resistance(df),
}
```

def get_coins() -> list:
return watchlist if watchlist else DEFAULT_COINS

# ══════════════════════════════════════════════════════════════════════════════

# TELEGRAM KOMANDALAR

# ══════════════════════════════════════════════════════════════════════════════

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update):
await update.message.reply_text(“⛔ İcazəniz yoxdur.”)
return
keyboard = [
[InlineKeyboardButton(“💰 Balans”,       callback_data=“balance”),
InlineKeyboardButton(“📋 Watchlist”,     callback_data=“watchlist_show”)],
[InlineKeyboardButton(“📊 Analiz”,        callback_data=“analyze_menu”),
InlineKeyboardButton(“📈 Siqnallar”,     callback_data=“signals_menu”)],
[InlineKeyboardButton(“🟢 BUY”,           callback_data=“buy_menu”),
InlineKeyboardButton(“🔴 SELL”,          callback_data=“sell_menu”)],
[InlineKeyboardButton(“🛑 Stop-Loss/TP”,  callback_data=“sltp_menu”),
InlineKeyboardButton(“🔔 Qiymət Alerti”, callback_data=“alert_menu”)],
[InlineKeyboardButton(“⚙️ Coin Əlavə Et”, callback_data=“add_coin”),
InlineKeyboardButton(“❓ Yardım”,         callback_data=“help_menu”)],
]
await update.message.reply_text(
“👋 *MEXC Spot Trade Botu*\n\nAşağıdan əməliyyat seçin:”,
reply_markup=InlineKeyboardMarkup(keyboard),
parse_mode=“Markdown”
)

async def cmd_balance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
try:
bal   = get_balance()
lines = [“💼 *SPOT Balans:*”]
for coin, amount in bal.items():
lines.append(f”  `{coin}`: `{amount}`”)
await update.message.reply_text(”\n”.join(lines), parse_mode=“Markdown”)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
if not ctx.args:
await update.message.reply_text(“İstifadə: `/price BTC/USDT`”, parse_mode=“Markdown”)
return
try:
symbol = ctx.args[0].upper()
price  = get_price(symbol)
await update.message.reply_text(f”💹 *{symbol}* = `{price}` USDT”, parse_mode=“Markdown”)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_analyze(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
“”“İstifadə: /analyze BTC/USDT [timeframe]  (1m 5m 15m 1h 4h 1d)”””
if not is_authorized(update): return
if not ctx.args:
await update.message.reply_text(“İstifadə: `/analyze BTC/USDT 1h`”, parse_mode=“Markdown”)
return
symbol    = ctx.args[0].upper()
timeframe = ctx.args[1] if len(ctx.args) > 1 else “1h”
try:
await update.message.reply_text(f”⏳ *{symbol}* ({timeframe}) analiz edilir…”, parse_mode=“Markdown”)
df     = get_ohlcv(symbol, timeframe)
result = generate_signal(df)
price  = get_price(symbol)
sr     = result[“sr”]

```
    sr_text = ""
    if sr["support1"]:    sr_text += f"  🟢 Dəstək 1:    `{sr['support1']}`\n"
    if sr["support2"]:    sr_text += f"  🟢 Dəstək 2:    `{sr['support2']}`\n"
    if sr["resistance1"]: sr_text += f"  🔴 Müqavimət 1: `{sr['resistance1']}`\n"
    if sr["resistance2"]: sr_text += f"  🔴 Müqavimət 2: `{sr['resistance2']}`\n"

    sig_text = "\n".join([f"  • {s}" for s in result["signals"]])

    msg = (
        f"📊 *{symbol} Texniki Analiz* ({timeframe})\n"
        f"{'─'*28}\n"
        f"💵 Qiymət: `{price}`\n"
        f"📈 Trend:  {result['trend']}\n"
        f"🎯 Siqnal: *{result['decision']}*\n\n"
        f"📉 *İndikatorlar:*\n"
        f"  RSI:   `{result['rsi']}`\n"
        f"  EMA9:  `{result['ema9']}`\n"
        f"  EMA21: `{result['ema21']}`\n\n"
        f"🏗 *Dəstək / Müqavimət:*\n{sr_text}\n"
        f"📌 *Siqnal Detalları:*\n{sig_text}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
except Exception as e:
    await update.message.reply_text(f"❌ Xəta: {e}")
```

async def cmd_signals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
“”“Watchlistdəki bütün coinlər üçün siqnal.”””
if not is_authorized(update): return
coins = get_coins()
await update.message.reply_text(f”⏳ {len(coins)} coin analiz edilir…”)
results = []
for symbol in coins:
try:
df     = get_ohlcv(symbol, “1h”, 60)
result = generate_signal(df)
price  = get_price(symbol)
results.append(f”*{symbol}* `{price}`\n  {result[‘trend’]} | {result[‘decision’]}”)
except Exception as e:
results.append(f”*{symbol}* ❌ {e}”)
msg = “📊 *Watchlist Siqnalları:*\n” + “─”*24 + “\n” + “\n\n”.join(results)
for i in range(0, len(msg), 4000):
await update.message.reply_text(msg[i:i+4000], parse_mode=“Markdown”)

async def cmd_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
if len(ctx.args) < 2:
await update.message.reply_text(“İstifadə: `/buy BTC/USDT 0.001`”, parse_mode=“Markdown”)
return
try:
symbol = ctx.args[0].upper()
amount = float(ctx.args[1])
order  = exchange.create_market_buy_order(symbol, amount)
price  = get_price(symbol)
await update.message.reply_text(
f”✅ *SPOT BUY verildi!*\nCüt: `{symbol}`\nMiqdar: `{amount}`\nQiymət: `{price}`\nOrder ID: `{order['id']}`”,
parse_mode=“Markdown”
)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_sell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
if len(ctx.args) < 2:
await update.message.reply_text(“İstifadə: `/sell BTC/USDT 0.001`”, parse_mode=“Markdown”)
return
try:
symbol = ctx.args[0].upper()
amount = float(ctx.args[1])
order  = exchange.create_market_sell_order(symbol, amount)
price  = get_price(symbol)
await update.message.reply_text(
f”✅ *SPOT SELL verildi!*\nCüt: `{symbol}`\nMiqdar: `{amount}`\nQiymət: `{price}`\nOrder ID: `{order['id']}`”,
parse_mode=“Markdown”
)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_limit_buy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
“”“İstifadə: /limitbuy BTC/USDT 0.001 95000”””
if not is_authorized(update): return
if len(ctx.args) < 3:
await update.message.reply_text(“İstifadə: `/limitbuy BTC/USDT 0.001 95000`”, parse_mode=“Markdown”)
return
try:
symbol, amount, price = ctx.args[0].upper(), float(ctx.args[1]), float(ctx.args[2])
order = exchange.create_limit_buy_order(symbol, amount, price)
await update.message.reply_text(
f”✅ *LIMIT BUY qoyuldu!*\nCüt: `{symbol}`\nMiqdar: `{amount}`\nHədəf: `{price}` USDT\nOrder ID: `{order['id']}`”,
parse_mode=“Markdown”
)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_limit_sell(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
“”“İstifadə: /limitsell BTC/USDT 0.001 105000”””
if not is_authorized(update): return
if len(ctx.args) < 3:
await update.message.reply_text(“İstifadə: `/limitsell BTC/USDT 0.001 105000`”, parse_mode=“Markdown”)
return
try:
symbol, amount, price = ctx.args[0].upper(), float(ctx.args[1]), float(ctx.args[2])
order = exchange.create_limit_sell_order(symbol, amount, price)
await update.message.reply_text(
f”✅ *LIMIT SELL qoyuldu!*\nCüt: `{symbol}`\nMiqdar: `{amount}`\nHədəf: `{price}` USDT\nOrder ID: `{order['id']}`”,
parse_mode=“Markdown”
)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_set_sltp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
“”“İstifadə: /sltp BTC/USDT 0.001 90000 105000”””
if not is_authorized(update): return
if len(ctx.args) < 4:
await update.message.reply_text(
“İstifadə: `/sltp BTC/USDT 0.001 90000 105000`\n_(symbol miqdar stop\*loss take\*profit)*”,
parse_mode=“Markdown”
)
return
try:
symbol = ctx.args[0].upper()
amount, sl, tp = float(ctx.args[1]), float(ctx.args[2]), float(ctx.args[3])
price  = get_price(symbol)
sl_tp_orders[symbol] = {“buy_price”: price, “sl”: sl, “tp”: tp, “amount”: amount}
await update.message.reply_text(
f”🛑 *SL/TP quruldu!*\nCüt: `{symbol}`\nGiriş: `{price}`\nStop-Loss: `{sl}` 🔴\nTake-Profit: `{tp}` 🟢\nMiqdar: `{amount}`\n\n_Bot avtomatik izləyir…*”,
parse_mode=“Markdown”
)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_show_sltp(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
if not sl_tp_orders:
await update.message.reply_text(“🛑 Aktiv SL/TP yoxdur.”)
return
lines = [“🛑 *Aktiv SL/TP:*”]
for sym, d in sl_tp_orders.items():
lines.append(f”\n*{sym}*\n  Giriş: `{d['buy_price']}`\n  SL: `{d['sl']}` | TP: `{d['tp']}`\n  Miqdar: `{d['amount']}`”)
await update.message.reply_text(”\n”.join(lines), parse_mode=“Markdown”)

async def cmd_set_alert(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
“”“İstifadə: /alert BTC/USDT above 100000”””
if not is_authorized(update): return
if len(ctx.args) < 3:
await update.message.reply_text(
“İstifadə:\n`/alert BTC/USDT above 100000`\n`/alert BTC/USDT below 90000`”,
parse_mode=“Markdown”
)
return
try:
symbol, direction, target = ctx.args[0].upper(), ctx.args[1].lower(), float(ctx.args[2])
if symbol not in price_alerts:
price_alerts[symbol] = {}
price_alerts[symbol][direction] = target
label = “yuxarı keçəndə ↑” if direction == “above” else “aşağı düşəndə ↓”
await update.message.reply_text(
f”🔔 *Alert quruldu!*\n`{symbol}` `{target}` USDT-ə {label} bildiriş göndəriləcək!”,
parse_mode=“Markdown”
)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_show_alerts(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
if not price_alerts:
await update.message.reply_text(“🔔 Aktiv alert yoxdur.”)
return
lines = [“🔔 *Aktiv Alertlər:*”]
for sym, directions in price_alerts.items():
for direction, target in directions.items():
lines.append(f”  `{sym}` {‘↑’ if direction == ‘above’ else ‘↓’} `{target}`”)
await update.message.reply_text(”\n”.join(lines), parse_mode=“Markdown”)

async def cmd_add_coin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
if not ctx.args:
await update.message.reply_text(“İstifadə: `/add PAXG/USDT`”, parse_mode=“Markdown”)
return
symbol = ctx.args[0].upper()
if symbol not in watchlist:
watchlist.append(symbol)
await update.message.reply_text(f”✅ `{symbol}` watchlist-ə əlavə edildi!”, parse_mode=“Markdown”)
else:
await update.message.reply_text(f”ℹ️ `{symbol}` artıq siyahıdadır.”, parse_mode=“Markdown”)

async def cmd_remove_coin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
if not ctx.args:
await update.message.reply_text(“İstifadə: `/remove BTC/USDT`”, parse_mode=“Markdown”)
return
symbol = ctx.args[0].upper()
if symbol in watchlist:
watchlist.remove(symbol)
await update.message.reply_text(f”🗑️ `{symbol}` siyahıdan silindi.”, parse_mode=“Markdown”)
else:
await update.message.reply_text(f”ℹ️ `{symbol}` siyahıda yoxdur.”, parse_mode=“Markdown”)

async def cmd_watchlist(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
coins = get_coins()
lines = [“📋 *Watchlist:*”]
for c in coins:
try:
price = get_price(c)
lines.append(f”  `{c}`: `{price}`”)
except:
lines.append(f”  `{c}`: —”)
await update.message.reply_text(”\n”.join(lines), parse_mode=“Markdown”)

async def cmd_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
symbol = ctx.args[0].upper() if ctx.args else “BTC/USDT”
try:
orders = exchange.fetch_open_orders(symbol)
if not orders:
await update.message.reply_text(f”📭 `{symbol}` üzrə açıq order yoxdur.”, parse_mode=“Markdown”)
return
lines = [f”📋 *Açıq Orderlər ({symbol}):*”]
for o in orders:
lines.append(f”• `{o['id']}` | {o[‘side’].upper()} | `{o['price']}` | `{o['amount']}`”)
await update.message.reply_text(”\n”.join(lines), parse_mode=“Markdown”)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
if len(ctx.args) < 2:
await update.message.reply_text(“İstifadə: `/cancel BTC/USDT ORDER_ID`”, parse_mode=“Markdown”)
return
try:
exchange.cancel_order(ctx.args[1], ctx.args[0].upper())
await update.message.reply_text(f”🗑️ Order `{ctx.args[1]}` ləğv edildi.”, parse_mode=“Markdown”)
except Exception as e:
await update.message.reply_text(f”❌ Xəta: {e}”)

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
if not is_authorized(update): return
msg = (
“📖 *Bütün Komandalar:*\n\n”
“*💰 Hesab:*\n”
“  /balance — Balans\n”
“  /watchlist — Coin siyahısı + qiymətlər\n”
“  /add PAXG/USDT — Coin əlavə et\n”
“  /remove BTC/USDT — Coin sil\n\n”
“*📊 Analiz:*\n”
“  /analyze BTC/USDT 1h — Texniki analiz\n”
“  /signals — Hamısı üçün siqnal\n”
“  /price BTC/USDT — Cari qiymət\n\n”
“*📈 Order:*\n”
“  /buy BTC/USDT 0.001 — Market al\n”
“  /sell BTC/USDT 0.001 — Market sat\n”
“  /limitbuy BTC/USDT 0.001 95000 — Limit al\n”
“  /limitsell BTC/USDT 0.001 105000 — Limit sat\n”
“  /orders BTC/USDT — Açıq orderlər\n”
“  /cancel BTC/USDT ID — Ləğv et\n\n”
“*🛑 Risk:*\n”
“  /sltp BTC/USDT 0.001 90000 105000\n”
“  /showsltp — Aktiv SL/TP-lər\n\n”
“*🔔 Alertlər:*\n”
“  /alert BTC/USDT above 100000\n”
“  /alert BTC/USDT below 90000\n”
“  /showalerts — Aktiv alertlər\n”
)
await update.message.reply_text(msg, parse_mode=“Markdown”)

# ── Inline Düymələr ────────────────────────────────────────────────────────────

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
query = update.callback_query
await query.answer()
data  = query.data

```
if data == "balance":
    bal   = get_balance()
    lines = ["💼 *SPOT Balans:*"]
    for coin, amount in bal.items():
        lines.append(f"  `{coin}`: `{amount}`")
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown")
elif data == "watchlist_show":
    coins = get_coins()
    lines = ["📋 *Watchlist:*"]
    for c in coins:
        try:
            lines.append(f"  `{c}`: `{get_price(c)}`")
        except:
            lines.append(f"  `{c}`: —")
    await query.edit_message_text("\n".join(lines), parse_mode="Markdown")
elif data == "analyze_menu":
    coins    = get_coins()
    keyboard = []
    row = []
    for i, coin in enumerate(coins):
        row.append(InlineKeyboardButton(coin, callback_data=f"ac_{coin}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 Geri", callback_data="back_main")])
    await query.edit_message_text(
        "📊 *Analiz üçün coin seçin:*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
elif data.startswith("ac_"):
    symbol = data[3:]
    await query.edit_message_text(f"⏳ *{symbol}* analiz edilir...", parse_mode="Markdown")
    try:
        df     = get_ohlcv(symbol, "1h")
        result = generate_signal(df)
        price  = get_price(symbol)
        sr     = result["sr"]
        sr_text = ""
        if sr["support1"]:    sr_text += f"  🟢 Dəstək 1:    `{sr['support1']}`\n"
        if sr["support2"]:    sr_text += f"  🟢 Dəstək 2:    `{sr['support2']}`\n"
        if sr["resistance1"]: sr_text += f"  🔴 Müqavimət 1: `{sr['resistance1']}`\n"
        if sr["resistance2"]: sr_text += f"  🔴 Müqavimət 2: `{sr['resistance2']}`\n"
        sig_text = "\n".join([f"  • {s}" for s in result["signals"]])
        msg = (
            f"📊 *{symbol} Texniki Analiz* (1h)\n"
            f"{'─'*28}\n"
            f"💵 Qiymət: `{price}`\n"
            f"📈 Trend:  {result['trend']}\n"
            f"🎯 Siqnal: *{result['decision']}*\n\n"
            f"📉 *İndikatorlar:*\n"
            f"  RSI:   `{result['rsi']}`\n"
            f"  EMA9:  `{result['ema9']}`\n"
            f"  EMA21: `{result['ema21']}`\n\n"
            f"🏗 *Dəstək / Müqavimət:*\n{sr_text}\n"
            f"📌 *Siqnal Detalları:*\n{sig_text}"
        )
        await query.edit_message_text(msg, parse_mode="Markdown")
    except Exception as e:
        await query.edit_message_text(f"❌ Xəta: {e}")
elif data == "back_main":
    keyboard = [
        [InlineKeyboardButton("💰 Balans",       callback_data="balance"),
         InlineKeyboardButton("📋 Watchlist",     callback_data="watchlist_show")],
        [InlineKeyboardButton("📊 Analiz",        callback_data="analyze_menu"),
         InlineKeyboardButton("📈 Siqnallar",     callback_data="signals_menu")],
        [InlineKeyboardButton("🟢 BUY",           callback_data="buy_menu"),
         InlineKeyboardButton("🔴 SELL",          callback_data="sell_menu")],
        [InlineKeyboardButton("🛑 Stop-Loss/TP",  callback_data="sltp_menu"),
         InlineKeyboardButton("🔔 Qiymət Alerti", callback_data="alert_menu")],
        [InlineKeyboardButton("⚙️ Coin Əlavə Et", callback_data="add_coin"),
         InlineKeyboardButton("❓ Yardım",         callback_data="help_menu")],
    ]
    await query.edit_message_text(
        "👋 *MEXC Spot Trade Botu*\n\nAşağıdan əməliyyat seçin:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
elif data == "signals_menu":
    await query.edit_message_text("Siqnallar: `/signals`\nTek coin: `/analyze BTC/USDT 1h`", parse_mode="Markdown")
elif data == "buy_menu":
    await query.edit_message_text("Market: `/buy BTC/USDT 0.001`\nLimit: `/limitbuy BTC/USDT 0.001 95000`", parse_mode="Markdown")
elif data == "sell_menu":
    await query.edit_message_text("Market: `/sell BTC/USDT 0.001`\nLimit: `/limitsell BTC/USDT 0.001 105000`", parse_mode="Markdown")
elif data == "sltp_menu":
    await query.edit_message_text("SL/TP: `/sltp BTC/USDT 0.001 90000 105000`\n_(symbol miqdar stop\\_loss take\\_profit)_", parse_mode="Markdown")
elif data == "alert_menu":
    await query.edit_message_text("Alert:\n`/alert BTC/USDT above 100000`\n`/alert BTC/USDT below 90000`", parse_mode="Markdown")
elif data == "add_coin":
    await query.edit_message_text("Əlavə et: `/add PAXG/USDT`\nSil: `/remove BTC/USDT`", parse_mode="Markdown")
elif data == "help_menu":
    await query.edit_message_text("Bütün komandalar üçün: `/help`", parse_mode="Markdown")
```

# ══════════════════════════════════════════════════════════════════════════════

# ARXA FONDA İZLƏMƏ (Alert + SL/TP) — hər 30 saniyə

# ══════════════════════════════════════════════════════════════════════════════

async def background_monitor(app):
await asyncio.sleep(15)
log.info(“✅ Arxa fon izləməsi başladı.”)

```
while True:
    try:
        # Qiymət alertləri
        triggered = []
        for symbol, directions in list(price_alerts.items()):
            try:
                price = get_price(symbol)
                for direction, target in list(directions.items()):
                    if direction == "above" and price >= target:
                        await app.bot.send_message(ALLOWED_USER_ID,
                            f"🔔 *Alert!* `{symbol}` = `{price}` USDT\nHədəf `{target}` ↑ keçildi!",
                            parse_mode="Markdown")
                        triggered.append((symbol, direction))
                    elif direction == "below" and price <= target:
                        await app.bot.send_message(ALLOWED_USER_ID,
                            f"🔔 *Alert!* `{symbol}` = `{price}` USDT\nHədəf `{target}` ↓ keçildi!",
                            parse_mode="Markdown")
                        triggered.append((symbol, direction))
            except:
                pass
        for symbol, direction in triggered:
            if symbol in price_alerts:
                price_alerts[symbol].pop(direction, None)

        # SL/TP
        triggered_sltp = []
        for symbol, data in list(sl_tp_orders.items()):
            try:
                price = get_price(symbol)
                if price <= data["sl"]:
                    order = exchange.create_market_sell_order(symbol, data["amount"])
                    await app.bot.send_message(ALLOWED_USER_ID,
                        f"🛑 *STOP-LOSS!* `{symbol}` = `{price}` USDT\nSatış edildi! `{order['id']}`",
                        parse_mode="Markdown")
                    triggered_sltp.append(symbol)
                elif price >= data["tp"]:
                    order = exchange.create_market_sell_order(symbol, data["amount"])
                    await app.bot.send_message(ALLOWED_USER_ID,
                        f"🎯 *TAKE-PROFIT!* `{symbol}` = `{price}` USDT\nSatış edildi! `{order['id']}`",
                        parse_mode="Markdown")
                    triggered_sltp.append(symbol)
            except:
                pass
        for symbol in triggered_sltp:
            sl_tp_orders.pop(symbol, None)

    except Exception as e:
        log.error(f"Monitor xətası: {e}")

    await asyncio.sleep(30)
```

async def post_init(app):
asyncio.create_task(background_monitor(app))

# ══════════════════════════════════════════════════════════════════════════════

# BOTUN İŞƏ SALINMASI

# ══════════════════════════════════════════════════════════════════════════════

def main():
app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()

```
handlers = [
    ("start",       start),
    ("help",        cmd_help),
    ("balance",     cmd_balance),
    ("price",       cmd_price),
    ("analyze",     cmd_analyze),
    ("signals",     cmd_signals),
    ("buy",         cmd_buy),
    ("sell",        cmd_sell),
    ("limitbuy",    cmd_limit_buy),
    ("limitsell",   cmd_limit_sell),
    ("sltp",        cmd_set_sltp),
    ("showsltp",    cmd_show_sltp),
    ("alert",       cmd_set_alert),
    ("showalerts",  cmd_show_alerts),
    ("orders",      cmd_orders),
    ("cancel",      cmd_cancel),
    ("add",         cmd_add_coin),
    ("remove",      cmd_remove_coin),
    ("watchlist",   cmd_watchlist),
]
for cmd, handler in handlers:
    app.add_handler(CommandHandler(cmd, handler))
app.add_handler(CallbackQueryHandler(button_handler))

log.info("🚀 Bot işə düşdü!")
app.run_polling()
```

if **name** == “**main**”:
main()