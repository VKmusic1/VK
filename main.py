import os
import threading
import logging
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)
import requests

# --- Настройка ---
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN     = os.getenv("BOT_TOKEN")
VK_APP_ID     = os.getenv("VK_APP_ID")
VK_APP_SECRET = os.getenv("VK_APP_SECRET")
APP_URL       = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")
PORT          = int(os.getenv("PORT", 5000))

if not all([BOT_TOKEN, VK_APP_ID, VK_APP_SECRET, APP_URL]):
    raise RuntimeError("Нужно задать BOT_TOKEN, VK_APP_ID, VK_APP_SECRET и APP_URL/RENDER_EXTERNAL_URL")

# Словарь для хранения user_token по chat_id
user_tokens: dict[int, str] = {}

# --- Flask для колбэка OAuth2 ---
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running"

@flask_app.route("/callback")
def vk_callback():
    code    = request.args.get("code")
    state   = request.args.get("state")      # тут chat_id
    chat_id = int(state) if state and state.isdigit() else None

    if not code or not chat_id:
        return "Missing code or state", 400

    # Обменяем code на access_token
    resp = requests.get("https://oauth.vk.com/access_token", params={
        "client_id":     VK_APP_ID,
        "client_secret": VK_APP_SECRET,
        "redirect_uri":  f"{APP_URL}/callback",
        "code":          code
    }).json()

    token = resp.get("access_token")
    if not token:
        return "VK auth failed", 400

    user_tokens[chat_id] = token

    # Отправим юзеру в Telegram уведомление
    Bot(BOT_TOKEN).send_message(
        chat_id=chat_id,
        text="✅ Авторизация VK прошла успешно! Теперь можно искать треки."
    )
    return "OK"

# Запускаем Flask в фоне
def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=run_flask, daemon=True).start()

# --- Telegram-бот ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Чтобы искать музыку, сначала авторизуйся командой /login"
    )

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    auth_url = (
        f"https://oauth.vk.com/authorize?"
        f"client_id={VK_APP_ID}&"
        f"display=page&"
        f"redirect_uri={APP_URL}/callback&"
        f"scope=audio&"
        f"response_type=code&"
        f"state={chat_id}"
    )
    await update.message.reply_text(
        f"Перейди по ссылке для авторизации:\n{auth_url}"
    )

async def search_vk_music(query: str, token: str):
    params = {
        "q":             query,
        "access_token":  token,
        "v":             "5.131",
        "count":         5
    }
    resp = requests.get("https://api.vk.com/method/audio.search", params=params).json()
    return resp.get("response", {}).get("items", [])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    token   = user_tokens.get(chat_id)
    if not token:
        return await update.message.reply_text("Сначала авторизуйся: /login")

    query  = update.message.text
    tracks = await search_vk_music(query, token)
    if not tracks:
        return await update.message.reply_text("Треки не найдены")

    keyboard = [
        [InlineKeyboardButton(f"{t['artist']} – {t['title']}", callback_data=f"dl_{t['url']}")]
        for t in tracks
    ]
    await update.message.reply_text(
        "Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def download_track(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q   = update.callback_query
    url = q.data.split("_", 1)[1]
    await q.edit_message_text("Скачиваю трек…")
    await context.bot.send_audio(
        chat_id=q.message.chat_id,
        audio=url,
        title="Трек из VK"
    )

# Создаём и запускаем polling
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("login", login))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(download_track, pattern="^dl_"))

if __name__ == "__main__":
    # close_loop=False чтобы не тормозить основной поток с Flask
    app.run_polling(close_loop=False)
