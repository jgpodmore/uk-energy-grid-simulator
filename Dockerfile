# Multi-stage build: compile the React frontend, then serve it from the
# FastAPI backend as a single deployable service (one process, one free
# hosting slot - see the "Deploying" section in README.md).

FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app ./app
COPY --from=frontend-build /app/frontend/dist /app/frontend_dist

ENV FRONTEND_DIST_DIR=/app/frontend_dist
EXPOSE 8000
# $PORT, when set (Render, Fly.io, etc. inject it at runtime), overrides the
# 8000 default - the shell form lets us expand that env var at container
# start rather than baking a fixed port into the image.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
