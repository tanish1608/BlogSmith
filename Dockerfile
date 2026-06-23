# ── Frontend build stage ──────────────────────────────────────────────────────
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

# ── Python runtime ────────────────────────────────────────────────────────────
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY blogsmith/ ./blogsmith/
COPY --from=frontend /frontend/dist ./frontend/dist

# Cloud Run injects $PORT.
ENV PORT=8080
CMD exec uvicorn blogsmith.api.main:app --host 0.0.0.0 --port ${PORT}
