# ── Stage 1: Build frontend ──
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend/kirabot
COPY frontend/kirabot/package.json frontend/kirabot/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/kirabot/ ./
RUN npm run build

# ── Stage 2: Python runtime ──
FROM python:3.11-slim
WORKDIR /app

# System deps for PDF/document parsing + curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# App source
COPY . .

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/kirabot/dist /app/frontend/kirabot/dist

# Railway injects $PORT; default 8000
ENV PORT=8000
EXPOSE 8000

# Copy startup script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Set FASTAPI_URL for web_app → rag_engine proxy (allow override)
ENV FASTAPI_URL=${FASTAPI_URL:-http://localhost:8001}

# Start both services
WORKDIR /app
CMD ["/app/start.sh"]
