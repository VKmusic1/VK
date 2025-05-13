import os
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from dotenv import load_dotenv
import logging

load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_TOKEN  = os.getenv("VK_TOKEN")
APP_URL   = os.getenv("APP_URL")  # например https://your-app.onrender.com

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(bot, None, workers=0, use_context=True)

# --- Handlers ---

def start(update: Update, context):
    update.message.reply_text("Введите название трека для поиска:")

def search_vk_music(query: str):
    url = "https://api.vk.com/method/audio.search"
    params = {"q": query, "access_token": VK_TOKEN, "v": "5.131"}
    resp = requests.get(url, params=params).json()
    return resp.get("response", {}).get("items", [])[:5]

def handle_message(update: Update, context):
    tracks = search_vk_music(update.message.text)
    if not tracks:
        return update.message.reply_text("Треки не найдены")
    keyboard = [
        [InlineKeyboardButton(f"{t['artist']} – {t['title']}",
            callback_data=f"download_{t['url']}")]
        for t in tracks
    ]
    update.message.reply_text("Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(keyboard))

def download_track(update: Update, context):
    q   = update.callback_query
    url = q.data.split("_", 1)[1]
    q.edit_message_text("Скачиваю трек...")
    bot.send_audio(chat_id=q.message.chat_id, audio=url, title="Трек из VK")

# Регистрируем
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
dp.add_handler(CallbackQueryHandler(download_track, pattern="^download_"))

# --- Flask для вебхуков ---
app = Flask(__name__)

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dp.process_update(update)
    return "OK"

@app.route("/")
def index():
    return "Bot is running"

if __name__ == "__main__":
    # ставим webhook на старте
    bot.delete_webhook()
    bot.set_webhook(f"{APP_URL}/{BOT_TOKEN}")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
