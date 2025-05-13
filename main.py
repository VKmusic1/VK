import os
import requests
import logging
import asyncio
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

# 1) Лоадим .env и ставим логирование
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_TOKEN  = os.getenv("VK_TOKEN")
APP_URL   = os.getenv("APP_URL")  # https://your-app.onrender.com

if not BOT_TOKEN or not VK_TOKEN or not APP_URL:
    raise RuntimeError("Нужно задать BOT_TOKEN, VK_TOKEN и APP_URL в .env")

# 2) Обработчики
async def start(update: Update, context):
    await update.message.reply_text("Введите название трека для поиска:")

async def search_vk_music(query: str):
    resp = requests.get(
        "https://api.vk.com/method/audio.search",
        params={"q": query, "access_token": VK_TOKEN, "v": "5.131"}
    ).json()
    return resp.get("response", {}).get("items", [])[:5]

async def handle_message(update: Update, context):
    tracks = await search_vk_music(update.message.text)
    if not tracks:
        return await update.message.reply_text("Треки не найдены")
    kb = [
        [InlineKeyboardButton(f"{t['artist']} – {t['title']}",
            callback_data=f"download_{t['url']}"
        )]
        for t in tracks
    ]
    await update.message.reply_text(
        "Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def download_track(update: Update, context):
    q = update.callback_query
    url = q.data.split("_", 1)[1]
    await q.edit_message_text("Скачиваю трек...")
    await context.bot.send_audio(
        chat_id=q.message.chat_id,
        audio=url,
        title="Трек из VK"
    )

# 3) Создаём Application и регистрируем
app_bot = Application.builder().token(BOT_TOKEN).build()
app_bot.add_handler(CommandHandler("start", start))
app_bot.add_handler(
    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
)
app_bot.add_handler(
    CallbackQueryHandler(download_track, pattern="^download_")
)

# 4) Flask для вебхуков
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running"

@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, app_bot.bot)
    # обрабатываем апдейт в новом цикле
    asyncio.run(app_bot.process_update(update))
    return "OK"

if __name__ == "__main__":
    # удаляем старый webhook и ставим новый
    asyncio.run(app_bot.bot.delete_webhook())
    asyncio.run(app_bot.bot.set_webhook(f"{APP_URL}/{BOT_TOKEN}"))
    # запускаем Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
