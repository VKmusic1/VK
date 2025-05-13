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

# --- Определяем Flask приложение и функцию запуска ---
app = Flask("")

@app.route("/")
def home():
    return "Bot is running"

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# --- Telegram-бот ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Введите название трека для поиска:")

async def search_vk_music(query: str):
    url = "https://api.vk.com/method/audio.search"
    params = {
        "q": query,
        "access_token": os.getenv("VK_TOKEN"),
        "v": "5.131"
    }
    response = requests.get(url, params=params).json()
    return response.get('response', {}).get('items', [])[:5]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    tracks = await search_vk_music(query)
    
    if not tracks:
        await update.message.reply_text("🚫 Треки не найдены")
        return

    keyboard = []
    for track in tracks:
        title = f"{track['artist']} - {track['title']}"
        callback_data = f"download_{track['url']}"
        keyboard.append([InlineKeyboardButton(title, callback_data=callback_data)])
    
    await update.message.reply_text(
        "🎵 Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    url = query.data.split('_', 1)[1]
    
    await query.edit_message_text("⏳ Скачиваю трек...")
    await context.bot.send_audio(
        chat_id=query.message.chat_id,
        audio=url,
        title="Трек из VK"
    )

async def main():
    # Удаляем webhook, если он был установлен
    await app_bot.bot.delete_webhook()
    # Запускаем polling
    await app_bot.run_polling()

if __name__ == "__main__":
    # Запускаем Flask сервер в отдельном потоке
    threading.Thread(target=run_flask).start()

    # Создаём Telegram-бота
    app_bot = Application.builder().token(os.environ['BOT_TOKEN']).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CallbackQueryHandler(download_track, pattern="^download_"))
    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    import asyncio
    asyncio.run(main())
