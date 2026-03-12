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

# System deps for PDF/document parsing + curl for health checks + bash for start.sh + 한글 폰트 (간트차트)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 curl bash \
    fonts-nanum fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# matplotlib 폰트 캐시 재생성 (한글 폰트 인식)
RUN python -c "import matplotlib.pyplot as plt; plt.figure()"

# Create non-root user
RUN groupadd -r app && useradd -r -g app app

# App source
COPY --chown=app:app . .

# Copy built frontend from stage 1
COPY --from=frontend-build --chown=app:app /app/frontend/kirabot/dist /app/frontend/kirabot/dist

# Railway injects $PORT; default 8000
ENV PORT=8000
EXPOSE 8000

# Copy startup script
COPY --chown=app:app start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Set FASTAPI_URL for web_app → rag_engine proxy (Railway can override)
ENV FASTAPI_URL=http://localhost:8001

# Create writable directories for non-root user
RUN mkdir -p /app/data /app/frontend/kirabot/dist \
    /app/rag_engine/data/company_db \
    /app/rag_engine/data/proposals && \
    chown -R app:app /app/data /app/frontend/kirabot/dist /app/rag_engine/data

# Switch to non-root user
USER app

# Start both services
WORKDIR /app
CMD ["/app/start.sh"]
