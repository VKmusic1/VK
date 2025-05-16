import os
import logging
import threading
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask
import asyncio
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)

# --- Загрузка переменных окружения и логирование ---
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_SID = os.getenv("VK_SID")
PORT = int(os.getenv("PORT", 5000))

print("DEBUG: BOT_TOKEN:", "SET" if BOT_TOKEN else "MISSING")
print("DEBUG: VK_SID:", VK_SID[:10] + "..." if VK_SID else "MISSING")
print("DEBUG: PORT:", PORT)

if not BOT_TOKEN or not VK_SID:
    print("ОШИБКА: Нет BOT_TOKEN или VK_SID в ENV. Проверь настройки!")
    raise RuntimeError("Нужно задать BOT_TOKEN и VK_SID в .env или переменных окружения")

# --- Принудительный сброс webhook (решает конфликт!) ---
async def delete_webhook_sync():
    await Bot(BOT_TOKEN).delete_webhook(drop_pending_updates=True)

print("DEBUG: Удаляем Webhook...")
asyncio.run(delete_webhook_sync())

# --- Минимальный Flask для Render ---
flask_app = Flask(__name__)

@flask_app.route("/")
def health_check():
    return "OK", 200

def run_flask():
    print("DEBUG: Flask сервер запущен на порту", PORT)
    flask_app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=run_flask, daemon=True).start()

# --- Поиск музыки на m.vk.com ---
def search_vk_mobile(query: str):
    print(f"DEBUG: Ищем VK: {query}")
    url = "https://m.vk.com/search"
    params = {"c[section]": "audio", "q": query}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/124.0.0.0 Safari/537.36"
    }
    cookies = {"remixsid": VK_SID}
    try:
        r = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=10)
    except Exception as e:
        print("ОШИБКА VK:", e)
        return []
    print("DEBUG: VK статус:", r.status_code)
    print("DEBUG: VK ответ (первые 500 символов):\n", r.text[:500])
    soup = BeautifulSoup(r.text, "html.parser")
    tracks = []
    for div in soup.find_all("div", attrs={"data-url": True}):
        url = div["data-url"]
        artist_el = div.select_one(".audio_row__performers, .audioRow__performers")
        title_el = div.select_one(".audio_row__title, .audioRow__title")
        if not (artist_el and title_el):
            continue
        tracks.append({
            "artist": artist_el.get_text(strip=True),
            "title":  title_el.get_text(strip=True),
            "url":    url
        })
        if len(tracks) >= 5:
            break
    print(f"DEBUG: Найдено треков: {len(tracks)}")
    return tracks

# --- Telegram-хэндлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("DEBUG: Обработан /start")
    await update.message.reply_text("Введите название трека для поиска:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.message.text.strip()
    print(f"DEBUG: handle_message: {q}")
    if not q:
        return
    tracks = search_vk_mobile(q)
    if not tracks:
        await update.message.reply_text("Треки не найдены.")
        print("DEBUG: Треки не найдены.")
        return
    kb = [
        [InlineKeyboardButton(f"{t['artist']} — {t['title']}", callback_data=f"dl_{t['url']}")]
        for t in tracks
    ]
    await update.message.reply_text("Результаты поиска:", reply_markup=InlineKeyboardMarkup(kb))

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cq = update.callback_query
    url = cq.data.split("_", 1)[1]
    print(f"DEBUG: Скачиваем аудио: {url}")
    await cq.edit_message_text("Скачиваю…")
    await context.bot.send_audio(chat_id=cq.message.chat_id, audio=url, title="Трек из VK")

# --- Запуск polling ---
if __name__ == "__main__":
    print("DEBUG: Запускаем Telegram polling...")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(download_track, pattern="^dl_"))
    app.run_polling()
