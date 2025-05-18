import requests
import sqlite3
import os
import asyncio
from telegram.ext import Application, CommandHandler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Update
from telegram.ext import ContextTypes

# Налаштування
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not YOUTUBE_API_KEY:
    raise ValueError("YOUTUBE_API_KEY не встановлено")
if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не встановлено")

# Ініціалізація бази даних
conn = sqlite3.connect("videos.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT,
        description TEXT,
        chat_id TEXT
    )
""")
conn.commit()

# Отримання опису відео
def get_video_description(video_id):
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YOUTUBE_API_KEY}"
        response = requests.get(url).json()
        if "items" in response and len(response["items"]) > 0:
            return response["items"][0]["snippet"]["description"]
        return None
    except Exception as e:
        print(f"Помилка YouTube API: {e}")
        return None

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привіт! Я бот для відстеження змін в описі YouTube-відео.\n"
        "Використовуй /track <video_id>, наприклад: /track ixqPzkuY_4U"
    )

# Команда /track
async def track_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Вкажи ID відео! Наприклад: /track ixqPzkuY_4U")
        return
    video_id = context.args[0]
    chat_id = str(update.message.chat_id)
    
    description = get_video_description(video_id)
    if description is None:
        await update.message.reply_text("Не вдалося знайти відео. Перевір ID.")
        return
    
    cursor.execute("SELECT * FROM videos WHERE video_id = ? AND chat_id = ?", (video_id, chat_id))
    if cursor.fetchone():
        await update.message.reply_text("Це відео вже відстежується!")
        return
    
    cursor.execute("INSERT INTO videos (video_id, description, chat_id) VALUES (?, ?, ?)", (video_id, description, chat_id))
    conn.commit()
    await update.message.reply_text(f"Відео {video_id} додано до відстеження!")

# Перевірка змін
async def check_descriptions():
    cursor.execute("SELECT video_id, description, chat_id FROM videos")
    for video_id, old_desc, chat_id in cursor.fetchall():
        new_desc = get_video_description(video_id)
        if new_desc and new_desc != old_desc:
            await application.bot.send_message(chat_id=chat_id, text=f"Опис відео {video_id} змінено:\nНовий опис: {new_desc}")
            cursor.execute("UPDATE videos SET description = ? WHERE video_id = ?", (new_desc, video_id))
            conn.commit()

# Налаштування бота
application = Application.builder().token(TELEGRAM_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("track", track_video))

# Періодична перевірка (30 хвилин)
scheduler = AsyncIOScheduler()
scheduler.add_job(check_descriptions, "interval", minutes=30)

# Асинхронна функція для запуску
async def main():
    scheduler.start()
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    await asyncio.Event().wait()

# Запуск бота
if __name__ == "__main__":
    print("Бот запускається...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Бот зупинений")