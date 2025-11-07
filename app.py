from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import instaloader
import re
import os

# ✅ Initialize FastAPI
app = FastAPI(
    title="Smart Media Downloader API",
    description="Download media links from Instagram, YouTube, TikTok, etc.",
    version="2.0"
)

# ✅ Enable CORS for public API / frontend / bots
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    """Root endpoint to check if API is working."""
    return {"message": "Welcome to Smart Media Downloader API 🚀"}


@app.get("/download")
def download_media(url: str):
    """
    Download media from multiple platforms.
    Example: /download?url=https://www.instagram.com/reel/xyz/
    """
    try:
        # 🟣 Handle Instagram URLs
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

        # 🔵 Handle Other Platforms (YouTube, TikTok, Facebook, Twitter, etc.)
        else:
            # Optional: use cookies.txt for login-required YouTube videos
            cookie_path = "cookies.txt" if os.path.exists("cookies.txt") else None

            ydl_opts = {
                "quiet": True,
                "skip_download": True,
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/mp4",
            }

            if cookie_path:
                ydl_opts["cookiefile"] = cookie_path

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    return {
                        "platform": info.get("extractor", "Unknown"),
                        "title": info.get("title"),
                        "duration": info.get("duration"),
                        "download_link": info.get("url"),
                        "thumbnail": info.get("thumbnail"),
                    }
                except Exception as e:
                    error_message = str(e)
                    # Handle YouTube "Sign in" or restricted errors gracefully
                    if "Sign in" in error_message or "login" in error_message:
                        return JSONResponse(
                            {"error": "This video requires login. Please upload cookies.txt or use a public video link."},
                            status_code=403,
                        )
                    return JSONResponse({"error": error_message}, status_code=500)

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
