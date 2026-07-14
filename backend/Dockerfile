FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/backend
RUN apt-get update && apt-get install -y --no-install-recommends curl ffmpeg && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml /tmp/backend/pyproject.toml
RUN mkdir -p /tmp/backend/app \
    && touch /tmp/backend/app/__init__.py \
    && pip install --no-cache-dir '/tmp/backend[dev]'
COPY backend /app/backend
COPY schemas /app/schemas
COPY scripts /app/scripts
RUN groupadd --gid 10001 meeting \
    && useradd --uid 10001 --gid meeting --create-home meeting \
    && mkdir -p /app/runtime /app/runtime/audio /tmp/meeting-copilot \
    && chown -R meeting:meeting /app/runtime /tmp/meeting-copilot
USER meeting
ENTRYPOINT ["/app/scripts/secure_entrypoint.sh"]

FROM base AS backend
CMD ["/app/scripts/container_api.sh"]

FROM base AS stt-worker
USER root
RUN pip install --no-cache-dir '/tmp/backend[stt]'
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.12/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.12/site-packages/nvidia/cudnn/lib
USER meeting
CMD ["uvicorn", "app.workers.stt_api:app", "--host", "0.0.0.0", "--port", "8001"]

FROM base AS tts-worker
USER root
RUN apt-get update && apt-get install -y --no-install-recommends espeak-ng && rm -rf /var/lib/apt/lists/*
USER meeting
CMD ["uvicorn", "app.workers.tts_api:app", "--host", "0.0.0.0", "--port", "8003"]
