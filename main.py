import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# --- Настройка и логирование ---
load_dotenv()
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_TOKEN  = os.getenv("VK_TOKEN")
if not BOT_TOKEN or not VK_TOKEN:
    raise RuntimeError("В .env должны быть BOT_TOKEN и VK_TOKEN")

# --- Поиск через официальный метод audio.search ---
def search_vk_music(query: str):
    params = {
        "q":            query,
        "access_token": VK_TOKEN,
        "v":            "5.131",
        "count":        5
    }
    r = requests.get("https://api.vk.com/method/audio.search", params=params)
    data = r.json()
    return data.get("response", {}).get("items", [])

# --- Хэндлеры бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название трека:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    if not q:
        return
    tracks = search_vk_music(q)
    if not tracks:
        return await update.message.reply_text("Треки не найдены.")
    kb = [
        [InlineKeyboardButton(f"{t['artist']} — {t['title']}",
                              callback_data=f"dl_{t['url']}")]
        for t in tracks
    ]
    await update.message.reply_text("Результаты:", reply_markup=InlineKeyboardMarkup(kb))

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq  = update.callback_query
    url = cq.data.split("_", 1)[1]
    await cq.edit_message_text("Скачиваю…")
    await context.bot.send_audio(chat_id=cq.message.chat_id, audio=url)

# --- Запуск polling ---
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(download_track, pattern="^dl_"))
    app.run_polling()
