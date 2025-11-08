# 🐍 Use an official lightweight Python base image
FROM python:3.11-slim

# 🧩 System setup: Install ffmpeg + dependencies required by browser_cookie3
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        libnss3 \
        libgconf-2-4 \
        libxss1 \
        libappindicator3-1 \
        fonts-liberation \
        wget \
        curl \
        gnupg \
        tzdata && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 🌍 Set timezone & environment variables
ENV TZ=Asia/Kolkata \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/root/.local/bin:$PATH"

# 📁 Set working directory
WORKDIR /app

# 📦 Copy project files to container
COPY . .

# 🧠 Install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir browser-cookie3==0.19.1

# 🔥 Optional: Pre-create cookies.txt if missing
RUN echo "# Netscape HTTP Cookie File" > /app/cookies.txt

# 🌐 Expose FastAPI / Uvicorn port
EXPOSE 10000

# 🚀 Start FastAPI app with Uvicorn (production mode)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000", "--proxy-headers"]
