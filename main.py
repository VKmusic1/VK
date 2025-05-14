# main.py

import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# --- Загрузка переменных окружения и логирование ---
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Нужно задать BOT_TOKEN в .env или в переменных окружения")

# --- Гарантированно сбросим любой webhook ---
bot = Bot(BOT_TOKEN)
bot.delete_webhook(drop_pending_updates=True)

# --- Парсинг аудио с мобильного VK ---
def search_vk_mobile(query: str):
    url = "https://m.vk.com/search"
    params = {"c[section]": "audio", "q": query}
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tracks = []
    for div in soup.find_all("div", class_="audio_row")[:5]:
        artist = div.find("div", class_="audio_row__performers")
        title  = div.find("div", class_="audio_row__title")
        src    = div.get("data-url")
        if artist and title and src:
            tracks.append({
                "artist": artist.get_text(strip=True),
                "title":  title.get_text(strip=True),
                "url":    src
            })
    return tracks

# --- Telegram-хэндлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название трека для поиска:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    if not query:
        return
    tracks = search_vk_mobile(query)
    if not tracks:
        return await update.message.reply_text("Треки не найдены.")
    keyboard = [
        [InlineKeyboardButton(
            f"{t['artist']} — {t['title']}",
            callback_data=f"dl_{t['url']}"
        )]
        for t in tracks
    ]
    await update.message.reply_text(
        "Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    url = cq.data.split("_", 1)[1]
    await cq.edit_message_text("Скачиваю…")
    await context.bot.send_audio(
        chat_id=cq.message.chat_id,
        audio=url,
        title="Трек из VK"
    )

# --- Запуск бота через polling ---
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(download_track, pattern="^dl_"))

    # Запускаем polling, конфликт webhook/getUpdates больше не возникнет
    app.run_polling()
