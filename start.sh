#!/bin/bash
set -e

echo "=== START.SH STARTING ==="
echo "Working directory: $(pwd)"
echo "User: $(whoami)"
echo "PORT: ${PORT:-8000}"

# OPENAI_API_KEY is required for all AI features (proposal, analysis, chat).
# Without it the service starts but every generation API returns 503.
# Fail fast here so Railway restart policy catches the misconfiguration
# instead of running a half-alive service that passes health checks.
if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "FATAL: OPENAI_API_KEY is not set. All AI features will fail."
  echo "Set the variable in Railway dashboard and redeploy."
  exit 1
fi

# Graceful shutdown handler
cleanup() {
  echo "Shutting down services..."
  kill $RAG_PID 2>/dev/null || true
  kill $MONITOR_PID 2>/dev/null || true
  wait $RAG_PID 2>/dev/null || true
  wait $MONITOR_PID 2>/dev/null || true
  exit 0
}

trap cleanup EXIT SIGTERM SIGINT

# Monitor rag_engine process health
monitor_rag_engine() {
  while kill -0 $RAG_PID 2>/dev/null; do
    sleep 5
  done
  echo "CRITICAL: rag_engine process died unexpectedly"
  exit 1
}

# Start rag_engine in background on port 8001
echo "Starting rag_engine on port 8001..."
if [ ! -d "/app/rag_engine" ]; then
  echo "ERROR: /app/rag_engine directory not found!"
  exit 1
fi
cd /app/rag_engine
echo "Changed to: $(pwd)"
echo "Starting uvicorn..."
python -m uvicorn main:app --host 0.0.0.0 --port 8001 \
  > /tmp/rag_engine.log 2>&1 &
RAG_PID=$!
echo "rag_engine started with PID: $RAG_PID"

# Start background monitor
monitor_rag_engine &
MONITOR_PID=$!

# Wait for rag_engine to be ready (health check polling)
echo "Waiting for rag_engine to be ready..."
for i in {1..20}; do
  # Check if process is still alive
  if ! kill -0 $RAG_PID 2>/dev/null; then
    echo "ERROR: rag_engine process died!"
    echo "=== rag_engine crash logs ==="
    cat /tmp/rag_engine.log
    exit 1
  fi

  if curl -s http://localhost:8001/healthz > /dev/null 2>&1; then
    echo "rag_engine is ready (attempt $i)"
    break
  fi

  if [ $i -eq 20 ]; then
    echo "ERROR: rag_engine failed to start within 20 seconds"
    echo "=== rag_engine startup logs ==="
    cat /tmp/rag_engine.log
    exit 1
  fi

  echo "Waiting for rag_engine... ($i/20)"
  sleep 1
done

# Warmup: Initialize ChromaDB before accepting user requests
echo "Warming up ChromaDB..."
if ! curl -s -f http://localhost:8001/warmup > /dev/null 2>&1; then
  echo "WARNING: ChromaDB warmup failed, but continuing anyway"
  echo "First user request may experience initialization delay"
fi
echo "ChromaDB warmup completed"

# Start web_app in foreground on $PORT (Railway default)
echo "Starting web_app on port ${PORT:-8000}..."
if [ ! -d "/app/services/web_app" ]; then
  echo "ERROR: /app/services/web_app directory not found!"
  exit 1
fi
# Run from /app root so "from services.web_app.*" absolute imports resolve naturally.
# Previous approach (cd to web_app + PYTHONPATH) failed because uvicorn's
# import_from_string resolves modules before sys.path modifications in the
# target module take effect.
cd /app
echo "Changed to: $(pwd)"
echo "Checking main.py..."
ls -la services/web_app/main.py
echo "Starting uvicorn on port ${PORT:-8000}..."
python -c "import uvicorn; uvicorn.run('services.web_app.main:app', host='0.0.0.0', port=int(__import__('os').environ.get('PORT', '8000')))"
