import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters
)
import vk_api

# 1) Загрузка .env и логирование
load_dotenv()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_TOKEN  = os.getenv("VK_TOKEN")    # для audio.search (но может не работать без логина)
VK_LOGIN  = os.getenv("VK_LOGIN")
VK_PASS   = os.getenv("VK_PASS")
APP_URL   = os.getenv("APP_URL") or os.getenv("RENDER_EXTERNAL_URL")

if not all([BOT_TOKEN, VK_LOGIN, VK_PASS, APP_URL]):
    raise RuntimeError("Нужно задать BOT_TOKEN, VK_LOGIN, VK_PASS и APP_URL/RENDER_EXTERNAL_URL")

# 2) Авторизуемся в VK через vk_api (даёт доступ к audio.search)
vk_session = vk_api.VkApi(VK_LOGIN, VK_PASS)
vk_session.auth(token_only=True)
vk = vk_session.get_api()

# 3) Хэндлеры бота
async def start(update: Update, context):
    await update.message.reply_text("Введите название трека для поиска:")

async def search_vk_music(query: str):
    try:
        result = vk.audio.search(q=query, count=5)
        return result.get("items", [])
    except Exception as e:
        logging.error("VK audio API error: %s", e)
        return []

async def handle_message(update: Update, context):
    tracks = await search_vk_music(update.message.text)
    if not tracks:
        return await update.message.reply_text("Треки не найдены")
    keyboard = [
        [InlineKeyboardButton(
            f"{t['artist']} – {t['title']}",
            callback_data=f"download_{t['url']}"
        )]
        for t in tracks
    ]
    await update.message.reply_text(
        "Результаты поиска:",
        reply_markup=InlineKeyboardMarkup(keyboard)
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

# 4) Собираем приложение и регистрируем хэндлеры
app = Application.builder().token(BOT_TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(CallbackQueryHandler(download_track, pattern="^download_"))

# 5) Запускаем в режиме webhook
if __name__ == "__main__":
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path=BOT_TOKEN,
        webhook_url=f"{APP_URL}/{BOT_TOKEN}"
    )
