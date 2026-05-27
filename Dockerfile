# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /build
COPY frontend-react/package*.json ./
RUN npm ci
COPY frontend-react/ ./
RUN npm run build

# Stage 2: Python Backend
FROM python:3.12-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY app/ app/
# Copy the legacy frontend just in case it's still needed somewhere
COPY frontend/ frontend/
# Copy the built React app from Stage 1
COPY --from=frontend-builder /build/dist frontend-react/dist/

# Create logs directory
RUN mkdir -p logs

# Health check
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD curl -f http://localhost:7860/health || exit 1

EXPOSE 7860

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
