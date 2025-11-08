from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp, instaloader, re, os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# ✅ Initialize FastAPI
app = FastAPI(
    title="Smart Media Downloader API + Telegram",
    description="Download media from Instagram, YouTube, TikTok, etc.",
    version="2.2"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Telegram bot setup
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
telegram_app = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! Send me a YouTube, Instagram, or TikTok link and I’ll get the download link for you.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    await update.message.reply_text("🔍 Fetching video info... Please wait ⏳")

    try:
        if "instagram.com" in url:
            shortcode = re.search(r"reel/([A-Za-z0-9_-]+)/", url)
            if not shortcode:
                await update.message.reply_text("❌ Invalid Instagram URL")
                return
            shortcode = shortcode.group(1)
            L = instaloader.Instaloader(save_metadata=False)
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            await update.message.reply_text(f"📸 Instagram Reel: {post.owner_username}\n🎬 {post.caption or ''}\n🔗 {post.video_url if post.is_video else post.url}")

        else:
            ydl_opts = {"quiet": True, "skip_download": True, "format": "best"}
            if os.path.exists("cookies.txt"):
                ydl_opts["cookiefile"] = "cookies.txt"

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Untitled")
                link = info.get("url")
                thumbnail = info.get("thumbnail")
                await update.message.reply_photo(thumbnail, caption=f"🎥 {title}\n📥 {link}")

    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")


# ✅ Start the Telegram Bot
@app.on_event("startup")
async def start_telegram_bot():
    global telegram_app
    if not BOT_TOKEN:
        print("⚠️ TELEGRAM_BOT_TOKEN not set in environment variables")
        return

    telegram_app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Smart Media Bot is live...")
    await telegram_app.start()
    await telegram_app.updater.start_polling()


@app.on_event("shutdown")
async def shutdown_telegram_bot():
    if telegram_app:
        await telegram_app.stop()


@app.get("/")
def home():
    return {"message": "Smart Media Downloader API + Telegram Bot running 🚀"}
