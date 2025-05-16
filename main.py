import os
import logging
import threading
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_SID = os.getenv("VK_SID")
PORT = int(os.getenv("PORT", 5000))

if not BOT_TOKEN or not VK_SID:
    raise RuntimeError("Нужно задать BOT_TOKEN и VK_SID в .env или переменных окружения")

# Flask для Render
flask_app = Flask(__name__)

@flask_app.route("/")
def health_check():
    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=run_flask, daemon=True).start()

# VK поиск
def search_vk_mobile(query: str):
    url = "https://m.vk.com/search"
    params = {"c[section]": "audio", "q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36"
    }
    cookies = {"remixsid": VK_SID}
    r = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=10)
    soup = BeautifulSoup(r.text, "html.parser")
    tracks = []
    for div in soup.find_all("div", attrs={"data-url": True}):
        url = div["data-url"]
        artist_el = div.select_one(".audio_row__performers, .audioRow__performers")
        title_el = div.select_one(".audio_row__title, .audioRow__title")
        if not (artist_el and title_el):
            continue
        tracks.append({
            "artist": artist_el.get_text(strip=True),
            "title":  title_el.get_text(strip=True),
            "url":    url
        })
        if len(tracks) >= 5:
            break
    return tracks

# Telegram хендлеры
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название трека для поиска:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if not q:
        return
    tracks = search_vk_mobile(q)
    if not tracks:
        await update.message.reply_text("Треки не найдены.")
        return
    kb = [
        [InlineKeyboardButton(f"{t['artist']} — {t['title']}", callback_data=f"dl_{t['url']}")]
        for t in tracks
    ]
    await update.message.reply_text("Результаты поиска:", reply_markup=InlineKeyboardMarkup(kb))

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    url = cq.data.split("_", 1)[1]
    await cq.edit_message_text("Скачиваю…")
    await context.bot.send_audio(chat_id=cq.message.chat_id, audio=url, title="Трек из VK")

if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    # --- Важно! сбрасывай webhook через Application ---
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(download_track, pattern="^dl_"))
    # Сброс вебхука в Application.run_polling:
    app.run_polling(drop_pending_updates=True)
