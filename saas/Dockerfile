# Build từ thư mục gốc repo:  docker build -f saas/Dockerfile -t gen-planner .
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates pandoc git nodejs npm \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY saas/requirements.txt ./saas-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r saas-requirements.txt
COPY . .
# Core agent mặc định: Antigravity CLI (cài vào /root/.local/bin). Claude Code CLI là engine dự phòng (tắt: --build-arg WITH_CLAUDE=0).
ARG WITH_CLAUDE=1
RUN curl -fsSL https://antigravity.google/cli/install.sh | bash \
    && if [ "$WITH_CLAUDE" = "1" ]; then npm install -g @anthropic-ai/claude-code; fi
ENV PATH=/root/.local/bin:$PATH GP_DATA=/data PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8080
CMD ["uvicorn", "saas.server.main:app", "--host", "0.0.0.0", "--port", "8080"]
