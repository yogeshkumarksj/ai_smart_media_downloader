from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp, instaloader, re, os, requests
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, filters, CallbackContext

# ======================================
# 🔐 Telegram Bot Token (Set in Render → Environment Variables)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)
# ======================================

# ✅ Initialize FastAPI
app = FastAPI(
    title="Smart Media Downloader + Telegram Bot",
    description="Download media links from YouTube, Instagram, TikTok, etc. — and Telegram integrated!",
    version="3.0"
)

# ✅ CORS for public API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# 🌍 Basic endpoints (same as before)
# =====================================================
@app.head("/")
def health_check():
    return {"status": "ok"}

@app.get("/")
def home():
    return {"message": "Welcome to Smart Media Downloader API 🚀"}

@app.get("/download")
def download_media(url: str):
    try:
        # 🟣 Instagram Handler
        if "instagram.com" in url:
            shortcode = re.search(r"reel/([A-Za-z0-9_-]+)/", url)
            if not shortcode:
                return JSONResponse({"error": "Invalid Instagram URL"}, status_code=400)
            shortcode = shortcode.group(1)
            L = instaloader.Instaloader(save_metadata=False, download_video_thumbnails=False)
            post = instaloader.Post.from_shortcode(L.context, shortcode)
            return {
                "platform": "Instagram",
                "media_type": "reel" if post.is_video else "image",
                "download_link": post.video_url if post.is_video else post.url,
                "caption": post.caption or "",
                "owner_username": post.owner_username,
            }

        # 🔵 YouTube / TikTok / Facebook
        cookie_path = "cookies.txt" if os.path.exists("cookies.txt") else None
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        }
        if cookie_path:
            ydl_opts["cookiefile"] = cookie_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "platform": info.get("extractor", "Unknown"),
                "title": info.get("title"),
                "duration": info.get("duration"),
                "download_link": info.get("url"),
                "thumbnail": info.get("thumbnail"),
            }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# =====================================================
# 🤖 Telegram Handlers
# =====================================================
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "👋 *Welcome to SmartAI Media Bot!*\n\n"
        "Send me any YouTube, Instagram, or Facebook video link — "
        "and I’ll fetch the download link instantly 🚀",
        parse_mode="Markdown",
    )

def handle_link(update: Update, context: CallbackContext):
    url = update.message.text.strip()
    update.message.reply_text("🔍 Fetching video info... Please wait ⏳")

    try:
        response = requests.get(
            "https://ai-smart-media-downloader.onrender.com/download",
            params={"url": url}
        )
        data = response.json()

        if "error" in data:
            update.message.reply_text(f"❌ {data['error']}")
            return

        title = data.get("title", "Untitled")
        platform = data.get("platform", "Unknown")
        link = data.get("download_link")
        thumb = data.get("thumbnail")

        if thumb:
            bot.send_photo(
                chat_id=update.message.chat_id,
                photo=thumb,
                caption=f"🎬 *{title}*\n📱 Platform: {platform}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📥 Download MP4", url=link)]]
                ),
            )
        else:
            update.message.reply_text(
                f"🎬 *{title}*\n📱 Platform: {platform}\n[📥 Download MP4]({link})",
                parse_mode="Markdown",
            )
    except Exception as e:
        update.message.reply_text(f"⚠️ Error: {e}")

# Register bot handlers
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))


# =====================================================
# 🌐 Telegram Webhook endpoints
# =====================================================
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, bot)
    dispatcher.process_update(update)
    return JSONResponse({"ok": True})

@app.get("/setwebhook")
def set_webhook():
    webhook_url = "https://ai-smart-media-downloader.onrender.com/webhook"
    set_hook = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook?url={webhook_url}")
    return {"webhook_response": set_hook.json()}
