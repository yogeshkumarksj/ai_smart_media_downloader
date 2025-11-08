import os
import re
import yt_dlp
import instaloader
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# === Environment variables ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = os.getenv("BASE_URL", "https://ai-smart-media-downloader.onrender.com").rstrip("/")

# === FastAPI setup ===
app = FastAPI(
    title="Smart Media Downloader API + Telegram (Webhook)",
    description="Download videos from Instagram, YouTube, TikTok, etc.",
    version="3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Telegram Bot setup ===
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None


# ========== HELPER FUNCTIONS ==========

def get_media_info(url: str):
    """Extract media details without downloading."""
    try:
        # Instagram
        if "instagram.com" in url:
            shortcode = re.search(r"reel/([A-Za-z0-9_-]+)/", url)
            if not shortcode:
                raise ValueError("Invalid Instagram reel URL")

            shortcode = shortcode.group(1)
            loader = instaloader.Instaloader(download_video_thumbnails=False, save_metadata=False)
            post = instaloader.Post.from_shortcode(loader.context, shortcode)

            return {
                "platform": "Instagram",
                "title": post.caption or "Instagram Reel",
                "thumbnail": post.url,
                "download_link": post.video_url if post.is_video else post.url,
                "owner": post.owner_username,
            }

        # YouTube / TikTok / Facebook
        ydl_opts = {"quiet": True, "skip_download": True, "format": "best"}
        if os.path.exists("cookies.txt"):
            ydl_opts["cookiefile"] = "cookies.txt"

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                "platform": info.get("extractor", "Unknown"),
                "title": info.get("title", "Untitled"),
                "thumbnail": info.get("thumbnail"),
                "download_link": info.get("url"),
            }

    except Exception as e:
        raise Exception(f"Error fetching media info: {e}")


# ========== TELEGRAM WEBHOOK ==========

@app.get("/setwebhook")
async def set_webhook():
    """Manually call this once to connect Telegram bot to Render server."""
    if not bot:
        return {"error": "TELEGRAM_BOT_TOKEN not set"}

    webhook_url = f"{BASE_URL}/webhook"
    success = await bot.set_webhook(webhook_url)
    return {"success": success, "webhook_url": webhook_url}



@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram messages via webhook."""
    if not bot:
        return JSONResponse({"error": "Bot token missing"}, status_code=500)

    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return JSONResponse({"ok": True})

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip() if "text" in message else ""

    # /start command
    if text.startswith("/start"):
        await bot.send_message(
            chat_id,
            "👋 Hi! I’m your Smart Media Downloader Bot.\n\n"
            "Send me any YouTube, Instagram, or TikTok video link to get a download link instantly 🎥",
        )
        return JSONResponse({"ok": True})

    # Invalid text
    if not text or not any(x in text for x in ["youtube", "youtu.be", "instagram", "tiktok", "facebook"]):
        await bot.send_message(chat_id, "⚠️ Please send a valid media URL.")
        return JSONResponse({"ok": True})

    # Notify user
    await bot.send_message(chat_id, "🔍 Fetching video info... Please wait ⏳")

    # Fetch media info
    try:
        info = get_media_info(text)
    except Exception as e:
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")
        return JSONResponse({"ok": True})

    # Send response
    title = info.get("title", "Untitled")
    platform = info.get("platform", "Unknown")
    download_link = info.get("download_link")
    thumbnail = info.get("thumbnail")

    caption = f"🎬 *{title}*\n📱 Platform: {platform}\n🔗 [Download Video]({download_link})"

    try:
        if thumbnail:
            await bot.send_photo(
                chat_id=chat_id,
                photo=thumbnail,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📥 Download MP4", url=download_link)]]
                ),
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📥 Download MP4", url=download_link)]]
                ),
            )
    except Exception:
        await bot.send_message(chat_id, f"🎬 {title}\n📥 {download_link}")

    return JSONResponse({"ok": True})


# ========== API ENDPOINTS ==========

@app.get("/")
def home():
    return {"message": "Smart Media Downloader + Telegram Webhook API 🚀"}


@app.get("/download")
def api_download(url: str):
    """Optional REST API endpoint for frontend or manual testing."""
    try:
        info = get_media_info(url)
        return info
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

