import os
import logging
import threading
from dotenv import load_dotenv
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from googleapiclient.discovery import build
import yt_dlp

# --- ENV ---
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
PORT = int(os.getenv("PORT", 5000))

if not BOT_TOKEN or not YOUTUBE_API_KEY:
    raise RuntimeError("Нужно задать BOT_TOKEN и YOUTUBE_API_KEY в .env или переменных окружения")

# --- LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# --- FLASK (для Render Healthcheck) ---
flask_app = Flask(__name__)
@flask_app.route("/")
def health_check():
    return "OK", 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT)

threading.Thread(target=run_flask, daemon=True).start()

# --- YouTube Search ---
def search_youtube(query):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    req = youtube.search().list(q=query, part='snippet', type='video', maxResults=1)
    res = req.execute()
    items = res.get("items", [])
    if not items:
        return None, None
    video_id = items[0]["id"]["videoId"]
    title = items[0]["snippet"]["title"]
    return f"https://www.youtube.com/watch?v={video_id}", title

# --- HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Введите название трека или исполнителя для поиска на YouTube:")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text.strip()
    yt_url, yt_title = search_youtube(query)
    if not yt_url:
        await update.message.reply_text("Видео не найдено на YouTube.")
        return
    await update.message.reply_text(f"Найдено: {yt_title}\nСкачиваю аудио...")

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': 'audio.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
        }],
        'noplaylist': True,
        'quiet': True,
        'nocheckcertificate': True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(yt_url, download=True)
            file_name = ydl.prepare_filename(info)
            file_name = file_name.rsplit('.', 1)[0] + '.mp3'
        with open(file_name, "rb") as audio_file:
            await update.message.reply_audio(audio_file, title=yt_title)
        os.remove(file_name)
    except Exception as e:
        await update.message.reply_text(f"Ошибка при скачивании: {e}")

# --- MAIN ---
if __name__ == "__main__":
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(drop_pending_updates=True)
