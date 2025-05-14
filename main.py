import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# 1) Настройка
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Нужно задать BOT_TOKEN в .env")

# 2) Функция парсинга mobile-страницы VK
def search_vk_mobile(query: str):
    url = "https://m.vk.com/search"
    params = {
        "c[section]": "audio",
        "q": query
    }
    headers = {
        # Имитация браузера, чтобы выдавали HTML со списком
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    resp = requests.get(url, params=params, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tracks = []
    # каждый трек лежит в div.audio_row
    for div in soup.find_all("div", class_="audio_row")[:5]:
        artist = div.find("div", class_="audio_row__performers")
        title  = div.find("div", class_="audio_row__title")
        src    = div.get("data-url")  # ссылка на mp3

        if not (artist and title and src):
            continue

        tracks.append({
            "artist": artist.get_text(strip=True),
            "title":  title.get_text(strip=True),
            "url":    src
        })
    return tracks

# 3) Telegram-хэндлеры
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
        [
            InlineKeyboardButton(
                f"{t['artist']} — {t['title']}",
                callback_data=f"dl_{t['url']}"
            )
        ]
        for t in tracks
    ]
    await update.message.reply_text(
        "Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    url = q.data.split("_", 1)[1]
    await q.edit_message_text("Скачиваю…")
    await context.bot.send_audio(
        chat_id=q.message.chat_id,
        audio=url,
        title="Трек из VK"
    )

# 4) Сборка и запуск бота
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )
    app.add_handler(
        CallbackQueryHandler(download_track, pattern="^dl_")
    )

    # polling; close_loop=False чтобы не сбивать Flask (если он был бы)
    app.run_polling(close_loop=False)
