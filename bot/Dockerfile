FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc ffmpeg p7zip-full curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Cloudflare Tunnel client (the bot starts/stops it from Settings -> Web app)
RUN ARCH=$(dpkg --print-architecture) && \
    (curl -fsSL -o /usr/local/bin/cloudflared "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}" \
     && chmod +x /usr/local/bin/cloudflared) || echo "cloudflared not installed"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
