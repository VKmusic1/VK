import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# --- Настройка и логирование ---
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("Нужно задать BOT_TOKEN в .env или в переменных окружения")

# --- Гарантированно сбросим вебхук (чтобы не было Conflict) ---
bot = Application.builder().token(BOT_TOKEN).build().bot
bot.delete_webhook(drop_pending_updates=True)

# --- Парсер мобильной выдачи VK ---
def search_vk_mobile(query: str):
    resp = requests.get(
        "https://m.vk.com/search",
        params={"c[section]": "audio", "q": query},
        headers={"User-Agent": "Mozilla/5.0"}
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    tracks = []
    # ищем все элементы с data-url (ссылкой на mp3)
    for div in soup.find_all("div", attrs={"data-url": True}):
        url = div["data-url"]
        # класс мог смениться, поэтому несколько вариантов селекторов
        artist_el = div.select_one(
            ".audio_row__performers, .audioRow__performers, .audio_row__artist, .audioRow__artist"
        )
        title_el = div.select_one(
            ".audio_row__title, .audioRow__title, .audio_row__name, .audioRow__name"
        )
        if not (artist_el and title_el):
            continue
        artist = artist_el.get_text(strip=True)
        title  = title_el.get_text(strip=True)
        tracks.append({"artist": artist, "title": title, "url": url})
        if len(tracks) >= 5:
            break

    return tracks

# --- Handlers для Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название трека для поиска:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if not q:
        return
    tracks = search_vk_mobile(q)
    if not tracks:
        return await update.message.reply_text("Треки не найдены.")
    keyboard = [
        [InlineKeyboardButton(f"{t['artist']} — {t['title']}", callback_data=f"dl_{t['url']}")]
        for t in tracks
    ]
    await update.message.reply_text("Результаты поиска:", reply_markup=InlineKeyboardMarkup(keyboard))

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq  = update.callback_query
    url = cq.data.split("_", 1)[1]
    await cq.edit_message_text("Скачиваю…")
    await context.bot.send_audio(chat_id=cq.message.chat_id, audio=url, title="Трек из VK")

# --- Запуск бота через polling ---
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(download_track, pattern="^dl_"))
    app.run_polling()
