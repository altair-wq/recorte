# Recorte: one container with the FastAPI backend, the built React frontend, ffmpeg (libass) and the offline demo fixtures.
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent
COPY frontend ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend backend
COPY --from=web /app/frontend/dist frontend/dist
# Build the offline demo source + a pre-rendered fallback clip into the image (no network, no keys needed).
WORKDIR /app/backend
RUN python -m scripts.make_fixtures
ENV DEMO_MODE=1 PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
