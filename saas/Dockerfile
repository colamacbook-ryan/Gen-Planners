# Build từ thư mục gốc repo:  docker build -f saas/Dockerfile -t gen-planner .
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates pandoc git nodejs npm \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY saas/requirements.txt ./saas-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r saas-requirements.txt
COPY . .
# Core agent mặc định: Antigravity CLI (cài vào /usr/local/bin để user gpagent chạy được). Claude Code CLI là engine dự phòng (tắt: --build-arg WITH_CLAUDE=0).
ARG WITH_CLAUDE=1
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash -s -- --dir /usr/local/bin \
    && if [ "$WITH_CLAUDE" = "1" ]; then npm install -g @anthropic-ai/claude-code; fi
# User riêng cho core agent: agent chạy dưới user này, không đọc được app.db, khoá mã hoá hay dự án người khác
RUN useradd -r -m -d /home/gpagent -s /usr/sbin/nologin gpagent
# FORWARDED_ALLOW_IPS: chỉ tin X-Forwarded-For từ reverse proxy của bạn (đặt IP/CIDR của proxy). KHÔNG đặt "*" —
# ai cũng giả được IP và vượt giới hạn dò mật khẩu theo IP.
ENV GP_DATA=/data PYTHONUNBUFFERED=1 FORWARDED_ALLOW_IPS=127.0.0.1
VOLUME /data
EXPOSE 8080
# --proxy-headers: lấy IP thật của người dùng khi đứng sau reverse proxy (chống dò mật khẩu theo IP) — chỉ từ FORWARDED_ALLOW_IPS
CMD ["uvicorn", "saas.server.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
