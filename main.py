import os
import logging
import threading
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# ---- Настройка и логирование ----
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_SID    = os.getenv("VK_SID")
PORT      = int(os.getenv("PORT", 5000))

if not BOT_TOKEN or not VK_SID:
    raise RuntimeError("Нужно задать в ENV BOT_TOKEN и VK_SID (cookie remixsid)")

# ---- Мини-Flask для Render Health Check ----
flask_app = Flask(__name__)
@flask_app.route("/")
def health_check():
    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=run_flask, daemon=True).start()

# ---- Сбрасываем webhook, чтобы не мешал polling ----
Bot(BOT_TOKEN).delete_webhook(drop_pending_updates=True)

# ---- Функция парсинга мобильного VK с cookie ----
def search_vk_mobile(query: str):
    url = "https://m.vk.com/search"
    params = {"c[section]": "audio", "q": query}
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = {"remixsid": VK_SID}
    r = requests.get(url, params=params, headers=headers, cookies=cookies)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    tracks = []
    for div in soup.find_all("div", attrs={"data-url": True})[:5]:
        artist_el = div.select_one(".audio_row__performers, .audioRow__performers")
        title_el  = div.select_one(".audio_row__title, .audioRow__title")
        src        = div["data-url"]
        if not (artist_el and title_el):
            continue
        tracks.append({
            "artist": artist_el.get_text(strip=True),
            "title":  title_el.get_text(strip=True),
            "url":    src
        })
    return tracks

# ---- Telegram-хэндлеры ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название трека для поиска:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if not q:
        return
    tracks = search_vk_mobile(q)
    if not tracks:
        return await update.message.reply_text("Треки не найдены.")
    kb = [
        [InlineKeyboardButton(f"{t['artist']} — {t['title']}", callback_data=f"dl_{t['url']}")]
        for t in tracks
    ]
    await update.message.reply_text("Результаты поиска:", reply_markup=InlineKeyboardMarkup(kb))

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq  = update.callback_query
    url = cq.data.split("_", 1)[1]
    await cq.edit_message_text("Скачиваю…")
    await context.bot.send_audio(chat_id=cq.message.chat_id, audio=url, title="Трек из VK")

# ---- Запуск polling ----
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(download_track, pattern="^dl_"))
    app.run_polling()
