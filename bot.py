import os
import yt_dlp
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters, CallbackQueryHandler
)

BOT_TOKEN = os.environ.get("BOT_TOKEN")  # Set your bot token as env variable
COOKIES_ENV = "IG_COOKIES"  # Instagram cookies environment variable
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# ---------- /start ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Send me a YouTube or Instagram video link and I’ll help you download it!\n\n"
        "⚡ For Instagram, make sure your IG cookies are set in environment variable."
    )

# ---------- /help ----------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *How to use this bot:*\n\n"
        "1️⃣ Send me a YouTube or Instagram link.\n"
        "2️⃣ Choose 'Download Video' or 'Download Audio'.\n"
        "3️⃣ Select quality → receive content ✅\n\n"
        "⚡ Instagram uses cookies from environment variable.\n"
        "🆕 Update cookies anytime using /setcookies <cookies_string>"
    )
    await update.message.reply_markdown(text)

# ---------- /about ----------
async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 *About This Bot*\n\n"
        "I can download YouTube 🎥 and Instagram 📸 videos/audio for you!\n"
        "⚡ Built with Python 3.13\n"
        "📦 Powered by yt-dlp + ffmpeg\n"
        "💡 Created by: @Sagar_3000"
    )
    await update.message.reply_markdown(text)

# ---------- /setcookies ----------
async def set_cookies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /setcookies <your_cookies_string>")
        return

    new_cookies = " ".join(context.args)
    temp_file = DOWNLOADS_DIR / "manual_cookies.txt"
    with open(temp_file, "w") as f:
        f.write(new_cookies)

    await update.message.reply_text("✅ Cookies updated. Instagram downloads will use these cookies.")

# ---------- Handle video link ----------
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    context.user_data["url"] = url  # Save link for later

    keyboard = [[InlineKeyboardButton("🎬 Download Video", callback_data="download")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Ye lijiye aapki Video -", reply_markup=reply_markup)

# ---------- Ask quality ----------
async def ask_quality(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("🎬 360p Video", callback_data="q_360")],
        [InlineKeyboardButton("🎬 720p Video", callback_data="q_720")],
        [InlineKeyboardButton("🎬 1080p Video", callback_data="q_1080")],
        [InlineKeyboardButton("🎵 Audio (MP3)", callback_data="q_audio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("📥 Choose format:", reply_markup=reply_markup)

# ---------- Handle quality choice ----------
async def quality_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    url = context.user_data.get("url")
    if not url:
        await query.edit_message_text("⚠️ No URL found. Please send the link again.")
        return

    choice = query.data.replace("q_", "")
    format_map = {
        "360": "bestvideo[height<=360]+bestaudio/best",
        "720": "bestvideo[height<=720]+bestaudio/best",
        "1080": "bestvideo[height<=1080]+bestaudio/best",
        "audio": "bestaudio/best"
    }
    ydl_format = format_map.get(choice, "best")

    await query.edit_message_text(f"📥 Downloading {choice}...")

    if choice == "audio":
        await download_audio(update, context, url, ydl_format)
    else:
        await download_video_with_progress(update, context, url, ydl_format)

# ---------- Progress hook ----------
def progress_hook(d):
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "").strip()
        if percent:
            print(f"⏳ Downloading... {percent}")

# ---------- Get Instagram cookies ----------
def get_instagram_cookies():
    # Priority: Manual cookies via /setcookies > Env variable
    manual_cookie_file = DOWNLOADS_DIR / "manual_cookies.txt"
    if manual_cookie_file.exists():
        with open(manual_cookie_file, "r") as f:
            content = f.read()
        temp_file = DOWNLOADS_DIR / "cookies_temp.txt"
        with open(temp_file, "w") as f:
            f.write(content)
        return temp_file

    # Fallback: environment variable
    ig_cookies = os.environ.get(COOKIES_ENV)
    if ig_cookies:
        temp_file = DOWNLOADS_DIR / "cookies_temp.txt"
        with open(temp_file, "w") as f:
            f.write(ig_cookies)
        return temp_file
    return None

# ---------- Video Downloader ----------
async def download_video_with_progress(update, context, url: str, format_code: str):
    chat_id = update.effective_chat.id if update.message else update.callback_query.message.chat.id
    msg = await context.bot.send_message(chat_id=chat_id, text="📥 Starting download...")

    file_path = None
    cookie_file = None
    try:
        ydl_opts = {
            "format": format_code,
            "outtmpl": str(DOWNLOADS_DIR / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "merge_output_format": "mp4",
            "progress_hooks": [progress_hook],
        }

        # Get Instagram cookies if URL is from Instagram
        if "instagram.com" in url.lower():
            cookie_file = get_instagram_cookies()
            if cookie_file:
                ydl_opts["cookies"] = str(cookie_file)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        file_size = os.path.getsize(file_path)
        with open(file_path, "rb") as video:
            if file_size < 200 * 1024 * 1024:
                await context.bot.send_video(chat_id=chat_id, video=video)
            else:
                await context.bot.send_document(chat_id=chat_id, document=video)

        await msg.edit_text("✅ Video sent successfully!")

    except yt_dlp.utils.DownloadError as e:
        if "login required" in str(e).lower():
            await context.bot.send_message(chat_id=chat_id,
                text="⚠️ Instagram cookies expired. Update with /setcookies.")
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        if cookie_file and cookie_file.exists():
            cookie_file.unlink()

# ---------- Audio Downloader ----------
async def download_audio(update, context, url: str, format_code: str):
    chat_id = update.effective_chat.id if update.message else update.callback_query.message.chat.id
    msg = await context.bot.send_message(chat_id=chat_id, text="🎵 Starting audio download...")

    file_path = None
    cookie_file = None
    try:
        ydl_opts = {
            "format": format_code,
            "outtmpl": str(DOWNLOADS_DIR / "%(title)s.%(ext)s"),
            "noplaylist": True,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}],
        }

        if "instagram.com" in url.lower():
            cookie_file = get_instagram_cookies()
            if cookie_file:
                ydl_opts["cookies"] = str(cookie_file)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info).replace(".webm", ".mp3").replace(".m4a", ".mp3")

        with open(file_path, "rb") as audio:
            await context.bot.send_audio(chat_id=chat_id, audio=audio)

        await msg.edit_text("✅ Audio sent successfully!")

    except yt_dlp.utils.DownloadError as e:
        if "login required" in str(e).lower():
            await context.bot.send_message(chat_id=chat_id,
                text="⚠️ Instagram cookies expired. Update with /setcookies.")
        else:
            await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")

    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"❌ Error: {str(e)}")

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        if cookie_file and cookie_file.exists():
            cookie_file.unlink()

# ---------- Cleanup downloads ----------
def cleanup_downloads():
    if DOWNLOADS_DIR.exists():
        for f in DOWNLOADS_DIR.iterdir():
            try:
                f.unlink()
            except:
                pass
    else:
        DOWNLOADS_DIR.mkdir()

# ---------- Main ----------
def main():
    cleanup_downloads()
    DOWNLOADS_DIR.mkdir(exist_ok=True)

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("setcookies", set_cookies))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    app.add_handler(CallbackQueryHandler(ask_quality, pattern="^download$"))
    app.add_handler(CallbackQueryHandler(quality_button, pattern="^q_"))

    print("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
