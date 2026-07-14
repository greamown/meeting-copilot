FROM mcr.microsoft.com/playwright:v1.55.0-noble
WORKDIR /app/e2e
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY e2e/package.json ./
RUN npm install
COPY e2e ./
RUN espeak-ng -s 135 -w /tmp/meeting.wav \
      "We must confirm the database migration before deployment. Morgan owns the action item." \
    && cp /tmp/meeting.wav /app/e2e/fake-mic.wav \
    && ffmpeg -loglevel error -y -i /tmp/meeting.wav -ar 16000 -ac 1 -f s16le /app/e2e/fixture.pcm \
    && rm /tmp/meeting.wav
CMD ["npm", "test"]
