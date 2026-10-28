FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# FFmpeg is required for optional metadata editing; build tools compile TgCrypto.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt
COPY . /app

EXPOSE 10000
CMD ["python", "bot.py"]
