# ── Stage 1: build dependencies ───────────────────────────────────────────────
FROM python:3.11-slim AS base

# System packages needed by yt-dlp and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM base AS runtime

WORKDIR /app

# Copy application source
COPY video.py .
COPY templates/ templates/

# Create the downloads folder (volume can be mounted here)
RUN mkdir -p downloads

# Expose the Flask / Socket.IO port
EXPOSE 5000

# Use eventlet worker for proper async Socket.IO support
CMD ["python", "-m", "gunicorn", \
     "--worker-class", "eventlet", \
     "-w", "1", \
     "--bind", "0.0.0.0:5000", \
     "video:app"]
