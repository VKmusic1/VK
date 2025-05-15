import os
import logging
import tempfile
import asyncio
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
from moviepy.editor import VideoFileClip, TextClip, CompositeVideoClip
import whisper

# Укажи токен своего бота здесь
TELEGRAM_TOKEN = 'ТВОЙ_ТОКЕН_ТУТ'

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

model = whisper.load_model("small")  # Можешь заменить на tiny, base, medium, large

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Отправь мне видео, и я наложу на него субтитры.')

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video or update.message.document
    if not video:
        await update.message.reply_text("Пожалуйста, отправь видео-файл.")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        video_file = os.path.join(tmpdir, "input.mp4")
        sub_file = os.path.join(tmpdir, "subs.srt")
        output_file = os.path.join(tmpdir, "output.mp4")

        # Скачиваем видео
        await update.message.reply_text("Скачиваю видео...")
        await video.get_file().download_to_drive(video_file)

        # Распознаём аудио и создаём SRT
        await update.message.reply_text("Генерирую субтитры...")
        result = model.transcribe(video_file, fp16=False)
        srt_text = whisper.utils.write_srt(result["segments"])

        # Сохраняем субтитры во временный файл
        with open(sub_file, "w", encoding="utf-8") as f:
            f.write(srt_text)

        # Накладываем субтитры на видео (ffmpeg должен быть установлен!)
        await update.message.reply_text("Накладываю субтитры на видео...")
        os.system(
            f'ffmpeg -y -i "{video_file}" -vf "subtitles={sub_file}:force_style=\'Fontsize=26,PrimaryColour=&H00FFFF00,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0\'" -c:a copy "{output_file}"'
        )

        # Отправляем результат
        await update.message.reply_text("Отправляю готовое видео...")
        with open(output_file, "rb") as f:
            await update.message.reply_video(f, caption="Вот твоё видео с субтитрами!")

async def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VIDEO | filters.Document.VIDEO, handle_video))
    print('Бот запущен')
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
