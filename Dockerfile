# syntax=docker/dockerfile:1

# ---- Stage 1: build the React dashboard ----
FROM node:20-slim AS webbuild
WORKDIR /web
COPY frontend/ ./
# Empty base => same-origin: the SPA is served by this very service.
ENV VITE_API_BASE=""
RUN npm install --no-audit --no-fund && npm run build

# ---- Stage 2: Python API that also serves the built dashboard ----
FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATA_BACKEND=firestore
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY backend/ ./backend/
COPY fixtures/ ./fixtures/
COPY --from=webbuild /web/dist ./frontend/dist
EXPOSE 8080
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
