import os
import re
import yt_dlp
import instaloader
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
import browser_cookie3

def auto_update_cookies():
    """Fetch valid cookies from local browser and save as cookies.txt"""
    try:
        cookies = browser_cookie3.chrome(domain_name=".youtube.com")
        with open("cookies.txt", "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for cookie in cookies:
                f.write(
                    f"{cookie.domain}\tTRUE\t/\tFALSE\t{int(cookie.expires or 0)}\t{cookie.name}\t{cookie.value}\n"
                )
        print("✅ Cookies successfully updated from browser.")
    except Exception as e:
        print(f"⚠️ Failed to update cookies automatically: {e}")


# === Configuration ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = os.getenv("BASE_URL", "https://ai-smart-media-downloader.onrender.com").rstrip("/")

app = FastAPI(title="Smart Media Downloader", version="3.5")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None
COOKIES_PATH = "cookies.txt"
TEMP_DIR = "downloads"
os.makedirs(TEMP_DIR, exist_ok=True)


# ---------- Helper Functions ----------

def is_valid_cookie_file(path: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        head = f.read(200)
        return "# Netscape HTTP Cookie File" in head or "Netscape" in head


def normalize_url(url: str) -> str:
    """Convert shorts or mobile links into watch?v= format."""
    if "shorts/" in url:
        video_id = re.search(r"shorts/([A-Za-z0-9_-]+)", url)
        if video_id:
            return f"https://www.youtube.com/watch?v={video_id.group(1)}"
    if "m.youtube.com" in url:
        return url.replace("m.youtube.com", "www.youtube.com")
    return url


def get_cookie_path() -> str | None:
    if is_valid_cookie_file(COOKIES_PATH):
        print("✅ Using valid cookies.txt")
        return COOKIES_PATH
    print("⚠️ No valid cookies.txt found")
    return None


def download_video(url: str) -> str:
    """Download video and return local file path."""
    cookie_path = get_cookie_path()
    output_path = os.path.join(TEMP_DIR, "%(id)s.%(ext)s")

    ydl_opts = {
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "format": "bestvideo+bestaudio/best",
        "noplaylist": True,
        "nocheckcertificate": True,
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            if not file_path.endswith(".mp4"):
                base = os.path.splitext(file_path)[0]
                new_path = base + ".mp4"
                os.rename(file_path, new_path)
                file_path = new_path
            return file_path
    except Exception as e:
        raise Exception(f"Download failed: {e}")


def get_video_info(url: str):
    """Fetch video metadata only (no download)."""
    url = normalize_url(url)
    cookie_path = get_cookie_path()

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "format": "best",
        "nocheckcertificate": True,
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            return {
                "id": info.get("id"),
                "title": info.get("title", "Untitled"),
                "thumbnail": info.get("thumbnail"),
                "platform": info.get("extractor", "YouTube"),
            }
        except Exception as e:
            raise Exception(f"Error fetching info: {e}")


# ---------- Telegram Webhook ----------

@app.get("/setwebhook")
async def set_webhook():
    if not bot:
        return {"error": "Missing TELEGRAM_BOT_TOKEN"}
    webhook_url = f"{BASE_URL}/webhook"
    try:
        success = await bot.set_webhook(webhook_url)
        if success:
            print(f"✅ Webhook set at {webhook_url}")
        return {"success": success, "webhook_url": webhook_url}
    except Exception as e:
        return {"error": str(e)}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    if not bot:
        return JSONResponse({"error": "Bot not configured"}, status_code=500)

    data = await request.json()
    message = data.get("message") or data.get("edited_message")
    if not message:
        return JSONResponse({"ok": True})

    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip() if "text" in message else ""

    if text.startswith("/start"):
        await bot.send_message(
            chat_id,
            "👋 Welcome to *Smart Media Downloader AI Bot*!\n\n"
            "Send me any YouTube, Shorts, Instagram, or TikTok link to download instantly 📽️",
            parse_mode="Markdown",
        )
        return JSONResponse({"ok": True})

    if not any(x in text for x in ["youtube", "youtu.be", "instagram", "tiktok", "facebook"]):
        await bot.send_message(chat_id, "⚠️ Please send a valid media URL.")
        return JSONResponse({"ok": True})

    await bot.send_message(chat_id, "🔍 Fetching video info... Please wait ⏳")

    try:
        info = get_video_info(text)
        video_id = info.get("id")
        title = info.get("title")
        thumb = info.get("thumbnail")

        download_url = f"{BASE_URL}/file/{video_id}"

        caption = (
            f"🎬 *{title}*\n"
            f"📱 Platform: {info.get('platform')}\n"
            f"🔗 [Click to Download MP4]({download_url})"
        )

        if thumb:
            await bot.send_photo(
                chat_id=chat_id,
                photo=thumb,
                caption=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📥 Download Now", url=download_url)]]
                ),
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=caption,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📥 Download MP4", url=download_url)]]
                ),
            )
    except Exception as e:
        await bot.send_message(chat_id, f"❌ Error: {str(e)}")

    return JSONResponse({"ok": True})


# ---------- Direct File Download ----------

@app.get("/file/{video_id}")
def stream_video(video_id: str):
    """Serve the downloaded video directly."""
    try:
        pattern = re.compile(r"[A-Za-z0-9_-]{5,}")
        if not pattern.match(video_id):
            return JSONResponse({"error": "Invalid video ID"}, status_code=400)

        file_path = os.path.join(TEMP_DIR, f"{video_id}.mp4")
        if not os.path.exists(file_path):
            # Redownload if not cached
            url = f"https://www.youtube.com/watch?v={video_id}"
            file_path = download_video(url)

        return FileResponse(file_path, media_type="video/mp4", filename=os.path.basename(file_path))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------- API & Health ----------

@app.get("/")
def home():
    return {"message": "Smart Media Downloader + Telegram Bot is running 🚀"}


@app.get("/download")
def download_endpoint(url: str):
    try:
        info = get_video_info(url)
        return info
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

