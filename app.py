import os
import re
import yt_dlp
import instaloader
import asyncio
import browser_cookie3
import threading
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

# === CONFIGURATION ===
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
BASE_URL = os.getenv("BASE_URL", "https://ai-smart-media-downloader.onrender.com").rstrip("/")
COOKIES_PATH = "cookies.txt"
TEMP_DIR = "downloads"
os.makedirs(TEMP_DIR, exist_ok=True)

bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None

app = FastAPI(title="Smart Media Downloader AI", version="4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ---------- COOKIES AUTO-UPDATE ----------
def write_cookie_file(cookies):
    with open(COOKIES_PATH, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for cookie in cookies:
            f.write(
                f"{cookie.domain}\tTRUE\t{cookie.path}\t{'TRUE' if cookie.secure else 'FALSE'}\t{int(cookie.expires or 0)}\t{cookie.name}\t{cookie.value}\n"
            )

def refresh_cookies():
    """Fetch fresh YouTube cookies every 24h."""
    while True:
        try:
            cookies = browser_cookie3.chrome(domain_name=".youtube.com")
            write_cookie_file(cookies)
            print("✅ YouTube cookies refreshed successfully")
        except Exception as e:
            print(f"⚠️ Cookie refresh failed: {e}")
        time.sleep(86400)  # 24 hours

def is_valid_cookie_file(path: str) -> bool:
    if not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return "# Netscape" in f.read(200)

def get_cookie_path() -> str | None:
    if is_valid_cookie_file(COOKIES_PATH):
        print("✅ Using valid cookies.txt")
        return COOKIES_PATH
    print("⚠️ No valid cookies.txt found")
    return None

threading.Thread(target=refresh_cookies, daemon=True).start()


# ---------- HELPERS ----------
def normalize_url(url: str) -> str:
    """Convert Shorts or mobile URLs to standard format."""
    if "shorts/" in url:
        match = re.search(r"shorts/([A-Za-z0-9_-]+)", url)
        if match:
            return f"https://www.youtube.com/watch?v={match.group(1)}"
    if "m.youtube.com" in url:
        return url.replace("m.youtube.com", "www.youtube.com")
    return url


def get_video_info(url: str):
    """Fetch video metadata only."""
    url = normalize_url(url)
    cookie_path = get_cookie_path()

    ydl_opts = {
    "quiet": True,
    "skip_download": True,  # or False if downloading
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
    "merge_output_format": "mp4",
    "noplaylist": True,
    "nocheckcertificate": True,
    "geo_bypass": True,
    "retries": 3,
    "age_limit": 0,
    "extract_flat": False,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.youtube.com/",
    },
    "cookiefile": "cookies.txt",  # absolute path also fine
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


def download_video(url: str) -> str:
    """Download video and return its local file path."""
    cookie_path = get_cookie_path()
    output_path = os.path.join(TEMP_DIR, "%(id)s.%(ext)s")

    ydl_opts = {
        "outtmpl": output_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
        "noplaylist": True,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "retries": 3,
    }

    if cookie_path:
        ydl_opts["cookiefile"] = cookie_path

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
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


# ---------- TELEGRAM WEBHOOK ----------
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
            "👋 *Welcome to Smart Media Downloader Bot*\n\n"
            "Just send me a YouTube, Shorts, Instagram, or TikTok link — and I’ll give you a direct download link 🎥",
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


# ---------- FILE STREAM ----------
@app.get("/file/{video_id}")
def serve_video(video_id: str):
    """Serve or re-download the requested video."""
    try:
        pattern = re.compile(r"^[A-Za-z0-9_-]{5,}$")
        if not pattern.match(video_id):
            return JSONResponse({"error": "Invalid video ID"}, status_code=400)

        file_path = os.path.join(TEMP_DIR, f"{video_id}.mp4")
        if not os.path.exists(file_path):
            url = f"https://www.youtube.com/watch?v={video_id}"
            file_path = download_video(url)

        return FileResponse(file_path, media_type="video/mp4", filename=os.path.basename(file_path))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# ---------- HEALTH & API ----------
@app.get("/")
def home():
    return {"message": "🚀 Smart Media Downloader + Telegram Bot is running."}


@app.get("/download")
def download_endpoint(url: str):
    try:
        info = get_video_info(url)
        return info
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

