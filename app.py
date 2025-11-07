from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import yt_dlp
import instaloader
import re

app = FastAPI(title="Smart Media Downloader API",
              description="Download media links from Instagram, YouTube, TikTok, etc.",
              version="1.0")

@app.get("/")
def home():
    return {"message": "Welcome to Smart Media Downloader API 🚀"}

@app.get("/download")
def download_media(url: str):
    """
    Download media from multiple platforms.
    Example: /download?url=https://www.instagram.com/reel/xyz/
    """
    try:
        # 🟣 Instagram Reels Handler
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
                "owner_username": post.owner_username
            }

        # 🔵 Other Platforms (YouTube, TikTok, Facebook, Twitter, etc.)
        else:
            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                "format": "best",
            }
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
