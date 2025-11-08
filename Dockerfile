# Use an official lightweight Python image
FROM python:3.11-slim

# Install FFmpeg (for yt_dlp to merge audio+video)
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

# Set working directory
WORKDIR /app

# Copy project files to container
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask default port
EXPOSE 10000

# Start your Flask app
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "10000"]
