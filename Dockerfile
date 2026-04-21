# ── SimuOrg Backend — GCP Cloud Run Dockerfile ──────────────────────────────
# Build context: project root (SimuOrg/)
# Run from root: docker build -t simuorg-backend .

FROM python:3.11-slim

WORKDIR /app

# System dependencies:
#   gcc       — required to compile psycopg2 C extensions
#   libpq-dev — PostgreSQL client libraries for psycopg2-binary
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (Docker layer cache — only re-runs if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full project (backend package + any shared modules)
COPY . .

# Cloud Run dynamically injects PORT — default to 8080 if running locally
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
