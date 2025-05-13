import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from dotenv import load_dotenv

load_dotenv()

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
    url = query.data.split('_')[1]
    
    await query.edit_message_text("⏳ Скачиваю трек...")
    await context.bot.send_audio(
        chat_id=query.message.chat_id,
        audio=url,
        title="Трек из VK"
    )

if __name__ == "__main__":
    app = Application.builder().token(os.getenv("BOT_TOKEN")).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(download_track, pattern="^download_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    app.run_polling()
