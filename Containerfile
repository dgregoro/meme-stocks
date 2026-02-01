# Meme Stocks Trading Application
# Multi-stage build: frontend build + backend runtime
# Uses Fedora per project platform preference

# ---------------------------------------------------------------------------
# Stage 1: Build frontend
# ---------------------------------------------------------------------------
FROM registry.fedoraproject.org/fedora:latest AS frontend-builder

RUN dnf install -y nodejs npm && dnf clean all

WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
# Use empty API base so built frontend calls same origin when served from backend
ENV VITE_API_BASE_URL=
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2: Backend runtime
# ---------------------------------------------------------------------------
FROM registry.fedoraproject.org/fedora:latest

RUN dnf install -y python3.11 python3-pip && dnf clean all

WORKDIR /app

# Backend dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend application
COPY backend/ ./backend/

# Frontend static files (from build stage)
COPY --from=frontend-builder /build/frontend/dist ./frontend_dist

# Persistence: /app/data for SQLite (override with volume)
ENV DATABASE_URL=sqlite:///./data/app.db

# Serve frontend from this container
ENV SERVING_FRONTEND=true

EXPOSE 8000

# Create data directory for SQLite
RUN mkdir -p /app/data

# Ensure /app is on PYTHONPATH for backend.app imports
ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
