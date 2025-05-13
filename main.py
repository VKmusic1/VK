import os
import threading
import requests
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from dotenv import load_dotenv

load_dotenv()

# --- Flask сервер для проверки, что приложение живо ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# --- Обработчики Telegram ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название трека для поиска:")

async def search_vk_music(query: str):
    url = "https://api.vk.com/method/audio.search"
    params = {
        "q": query,
        "access_token": os.getenv("VK_TOKEN"),
        "v": "5.131"
    }
    response = requests.get(url, params=params).json()
    return response.get("response", {}).get("items", [])[:5]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    tracks = await search_vk_music(query)
    if not tracks:
        await update.message.reply_text("Треки не найдены")
        return

    keyboard = [
        [
            InlineKeyboardButton(
                f"{t['artist']} – {t['title']}",
                callback_data=f"download_{t['url']}"
            )
        ]
        for t in tracks
    ]
    await update.message.reply_text(
        "Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    url = q.data.split("_", 1)[1]
    await q.edit_message_text("Скачиваю трек...")
    await context.bot.send_audio(
        chat_id=q.message.chat_id,
        audio=url,
        title="Трек из VK"
    )

if __name__ == "__main__":
    # 1) Старт Flask в отдельном потоке
    threading.Thread(target=run_flask, daemon=True).start()

    # 2) Создаём и настраиваем Telegram-бота
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise RuntimeError("Переменная BOT_TOKEN не задана в .env")

    application = (
        Application
        .builder()
        .token(bot_token)
        .build()
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(
        CallbackQueryHandler(download_track, pattern="^download_")
    )
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # 3) Старт polling (сам удалит старый webhook и запустит цикл событий)
    application.run_polling()
