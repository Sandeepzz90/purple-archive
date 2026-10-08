FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persistent media: uploads live inside the /app/data volume (data/media),
# so they survive redeploys. Boot copies repo-bundled photos in (no-clobber).
ENV MEDIA_DIR=/app/data/media

EXPOSE 8000
ENV PORT=8000

CMD ["sh", "-c", "mkdir -p /app/data/media && cp -n /app/Download/. /app/data/media/ 2>/dev/null; exec python server.py"]
