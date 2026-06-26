import os
import asyncio
import tempfile
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

# ============================================================
# НАСТРОЙКИ — ВСТАВЬ СВОИ ДАННЫЕ
# ============================================================
BOT_TOKEN = "ВСТАВЬ_ТОКЕН_СЮДА"
CHANNEL_INVITE = "https://t.me/+W2rPQf5R-lhiMTIy"
CHANNEL_CHAT_ID = -1002000000000  # ЗАМЕНИ НА ID СВОЕГО КАНАЛА
# ============================================================

user_urls = {}


async def check_subscription(user_id: int, bot) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_CHAT_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Ошибка проверки подписки: {e}")
        return False


def get_subscribe_keyboard():
    keyboard = [
        [InlineKeyboardButton("📢 Подписаться на канал", url=CHANNEL_INVITE)],
        [InlineKeyboardButton("✅ Я подписался", callback_data="check_sub")]
    ]
    return InlineKeyboardMarkup(keyboard)


def get_quality_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("360p", callback_data="quality_360"),
            InlineKeyboardButton("480p", callback_data="quality_480"),
        ],
        [
            InlineKeyboardButton("720p", callback_data="quality_720"),
            InlineKeyboardButton("1080p", callback_data="quality_1080"),
        ],
        [
            InlineKeyboardButton("🎵 MP3 (только звук)", callback_data="quality_mp3"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_subscribed = await check_subscription(user.id, context.bot)

    if is_subscribed:
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            "✅ Ты подписан на канал.\n\n"
            "🔗 Отправь мне ссылку на видео из YouTube, TikTok, Instagram, VK и других платформ!"
        )
    else:
        await update.message.reply_text(
            f"👋 Привет, {user.first_name}!\n\n"
            "⚠️ Для использования бота нужно подписаться на канал.\n\n"
            "👇 Нажми кнопку ниже, подпишись и нажми «Я подписался».",
            reply_markup=get_subscribe_keyboard()
        )


async def handle_check_sub(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    is_subscribed = await check_subscription(user.id, context.bot)

    if is_subscribed:
        await query.edit_message_text(
            "✅ Отлично! Ты подписан.\n\n"
            "🔗 Теперь отправь мне ссылку на видео!"
        )
    else:
        await query.edit_message_text(
            "❌ Ты ещё не подписан.\n\n"
            "Подпишись и нажми «Я подписался» снова.",
            reply_markup=get_subscribe_keyboard()
        )


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_subscribed = await check_subscription(user.id, context.bot)

    if not is_subscribed:
        await update.message.reply_text(
            "⚠️ Сначала подпишись на канал!",
            reply_markup=get_subscribe_keyboard()
        )
        return

    url = update.message.text.strip()

    if not (url.startswith("http://") or url.startswith("https://")):
        await update.message.reply_text("❌ Отправь корректную ссылку на видео.")
        return

    user_urls[user.id] = url

    await update.message.reply_text(
        "🎬 Ссылка получена! Выбери качество:",
        reply_markup=get_quality_keyboard()
    )


async def handle_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    quality = query.data.replace("quality_", "")

    url = user_urls.get(user.id)
    if not url:
        await query.edit_message_text("❌ Ссылка не найдена. Отправь ссылку ещё раз.")
        return

    format_map = {
        "360": "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]/best[height<=360]",
        "480": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best[height<=480]",
        "720": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best[height<=720]",
        "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]",
        "mp3": "bestaudio/best",
    }

    quality_label = {
        "360": "360p",
        "480": "480p",
        "720": "720p",
        "1080": "1080p",
        "mp3": "MP3 (аудио)",
    }

    await query.edit_message_text(
        f"⏳ Скачиваю в качестве {quality_label[quality]}...\n"
        "Подожди, это может занять до минуты."
    )

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_template = os.path.join(tmpdir, "%(title)s.%(ext)s")

            if quality == "mp3":
                ydl_opts = {
                    "format": format_map[quality],
                    "outtmpl": output_template,
                    "postprocessors": [{
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }],
                    "quiet": True,
                    "no_warnings": True,
                }
            else:
                ydl_opts = {
                    "format": format_map[quality],
                    "outtmpl": output_template,
                    "merge_output_format": "mp4",
                    "quiet": True,
                    "no_warnings": True,
                }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "video")

            files = os.listdir(tmpdir)
            if not files:
                raise Exception("Файл не скачан")

            filepath = os.path.join(tmpdir, files[0])
            file_size = os.path.getsize(filepath)

            if file_size > 52428800:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=(
                        f"❌ Файл слишком большой ({file_size // 1024 // 1024} МБ).\n"
                        "Telegram принимает файлы до 50 МБ.\n\n"
                        "Попробуй выбрать качество пониже."
                    )
                )
                return

            with open(filepath, "rb") as f:
                if quality == "mp3":
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=f,
                        title=title,
                        caption=f"🎵 {title}",
                    )
                else:
                    await context.bot.send_video(
                        chat_id=query.message.chat_id,
                        video=f,
                        caption=f"🎬 {title} [{quality_label[quality]}]",
                        supports_streaming=True,
                    )

            user_urls.pop(user.id, None)

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Private video" in error_msg:
            msg = "❌ Это приватное видео — скачать невозможно."
        elif "not available" in error_msg:
            msg = "❌ Видео недоступно или удалено."
        else:
            msg = "❌ Не удалось скачать видео. Проверь ссылку и попробуй снова."

        await context.bot.send_message(chat_id=query.message.chat_id, text=msg)

    except Exception as e:
        print(f"Ошибка: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Произошла ошибка. Попробуй ещё раз."
        )


def main():
    print("Бот запускается...")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_check_sub, pattern="^check_sub$"))
    app.add_handler(CallbackQueryHandler(handle_quality, pattern="^quality_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    print("Бот запущен!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
