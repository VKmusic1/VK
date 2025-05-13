import os
import requests
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

# 1) Загрузка .env и логирование
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_TOKEN  = os.getenv("VK_TOKEN")
# Подхват либо твоего APP_URL, либо Render выдаёт RENDER_EXTERNAL_URL
APP_URL   = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")

if not BOT_TOKEN or not VK_TOKEN or not APP_URL:
    raise RuntimeError("Нужно задать BOT_TOKEN, VK_TOKEN и APP_URL/RENDER_EXTERNAL_URL")

# 2) Хэндлеры
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
                              callback_data=f"download_{t['url']}")]
        for t in tracks
    ]
    await update.message.reply_text(
        "Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(kb)
    )

async def download_track(update: Update, context):
    q   = update.callback_query
    url = q.data.split("_", 1)[1]
    await q.edit_message_text("Скачиваю трек...")
    await context.bot.send_audio(
        chat_id=q.message.chat_id,
        audio=url,
        title="Трек из VK"
    )

# 3) Создаем Application и регистрируем хэндлеры
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(download_track, pattern="^download_"))

# 4) Запуск webhook-сервера
if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=BOT_TOKEN,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}"
    )
