import os
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)

# 1) Настройка и логирование
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
APP_URL   = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")
PORT      = int(os.getenv("PORT", "5000"))

if not BOT_TOKEN or not APP_URL:
    raise RuntimeError("Нужно задать BOT_TOKEN и APP_URL/RENDER_EXTERNAL_URL")

# 2) Синхронно сбрасываем любой старый webhook
delete_resp = requests.get(
    f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook?drop_pending_updates=true"
)
if not delete_resp.ok:
    logging.warning("deleteWebhook failed: %s", delete_resp.text)

# 3) Функция парсинга мобильного VK
def search_vk_mobile(query: str):
    resp = requests.get(
        "https://m.vk.com/search",
        params={"c[section]": "audio", "q": query},
        headers={"User-Agent": "Mozilla/5.0"}
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    tracks = []
    for div in soup.select("div.audio_row")[:5]:
        artist = div.select_one("div.audio_row__performers")
        title  = div.select_one("div.audio_row__title")
        url    = div.get("data-url")
        if artist and title and url:
            tracks.append({
                "artist": artist.get_text(strip=True),
                "title":  title.get_text(strip=True),
                "url":    url
            })
    return tracks

# 4) Хэндлеры бота
async def start(update: Update, context):
    await update.message.reply_text("Введите название трека для поиска:")

async def handle_search(update: Update, context):
    q = update.message.text.strip()
    if not q:
        return
    tracks = search_vk_mobile(q)
    if not tracks:
        return await update.message.reply_text("Треки не найдены.")
    kb = [
        [InlineKeyboardButton(f"{t['artist']} — {t['title']}", callback_data=f"dl_{t['url']}")]
        for t in tracks
    ]
    await update.message.reply_text("Результаты поиска:", reply_markup=InlineKeyboardMarkup(kb))

async def download_track(update: Update, context):
    cq  = update.callback_query
    url = cq.data.split("_", 1)[1]
    await cq.edit_message_text("Скачиваю…")
    await context.bot.send_audio(chat_id=cq.message.chat_id, audio=url, title="Трек из VK")

# 5) Сборка приложения и запуск webhook
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_search))
    app.add_handler(CallbackQueryHandler(download_track, pattern="^dl_"))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}"
    )
