FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
COPY backend /app/backend
COPY schemas /app/schemas
RUN pip install --no-cache-dir '/app/backend[stt]'
ENV PYTHONPATH=/app/backend MC_DATABASE_URL=sqlite+aiosqlite:////app/runtime/meeting-copilot.db
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
