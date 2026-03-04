#!/bin/bash
set -e

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
cd /app/rag_engine
python -m uvicorn main:app --host 0.0.0.0 --port 8001 \
  > /tmp/rag_engine.log 2>&1 &
RAG_PID=$!

# Start background monitor
monitor_rag_engine &
MONITOR_PID=$!

# Wait for rag_engine to be ready (health check polling)
echo "Waiting for rag_engine to be ready..."
for i in {1..30}; do
  if curl -s http://localhost:8001/healthz > /dev/null 2>&1; then
    echo "rag_engine is ready"
    break
  fi
  if [ $i -eq 30 ]; then
    echo "ERROR: rag_engine failed to start within 30 seconds"
    echo "=== rag_engine startup logs ==="
    cat /tmp/rag_engine.log
    exit 1
  fi
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
cd /app/services/web_app
python -c "import uvicorn; uvicorn.run('main:app', host='0.0.0.0', port=int(__import__('os').environ.get('PORT', '8000')))"
