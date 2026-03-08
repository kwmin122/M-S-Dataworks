FROM python:3.12-slim
WORKDIR /app

# Create non-root user
RUN groupadd -r app && useradd -r -g app app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:app . .

# Create writable directories
RUN mkdir -p /app/data && chown -R app:app /app/data

# Switch to non-root user
USER app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
