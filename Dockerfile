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

# System deps for PDF/document parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 \
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

# Start from the services/web_app directory so relative imports work
WORKDIR /app/services/web_app
CMD ["sh", "-c", "python -c \"import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=int(__import__('os').environ.get('PORT', '8000')))\""]
