# Stage 1: Build Next.js static export
FROM node:22-alpine AS frontend-builder
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Typst CLI binary extractor
FROM ghcr.io/typst/typst:latest AS typst-bin

# Stage 3: Python runtime with Playwright Chromium & Typst
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=127.0.0.1 \
    PORT=8000 \
    DATABASE_URL=sqlite:////app/data/jobs.db \
    ARTIFACTS_DIR=/app/artifacts \
    PROFILE_PATH=/app/profile/candidate_profile.yaml

# Install system dependencies for Playwright and runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-compiled Typst binary from official image
COPY --from=typst-bin /bin/typst /usr/local/bin/typst

# Copy and install Python dependencies
COPY pyproject.toml ./
RUN pip install --upgrade pip && \
    pip install . && \
    playwright install --with-deps chromium

# Copy application source and templates
COPY src/ ./src/
COPY templates/ ./templates/
COPY profile/ ./profile/
RUN pip install --no-deps -e .

# Copy compiled Next.js static export from Stage 1
COPY --from=frontend-builder /build/frontend/out/ ./frontend/out/

# Create runtime persistent mount points
RUN mkdir -p /app/data /app/artifacts

EXPOSE 8000

CMD ["uvicorn", "src.server.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
