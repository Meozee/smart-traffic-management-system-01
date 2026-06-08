# ═══════════════════════════════════════════════════════════════════════════════
# DOCKERFILE — STMS Backend FastAPI Server
# ═══════════════════════════════════════════════════════════════════════════════
# Build and run Smart Traffic Monitoring System API backend.
# Python 3.10 with YOLOv8, OpenCV, FastAPI, PostgreSQL support.
# ═══════════════════════════════════════════════════════════════════════════════

FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for OpenCV and runtime operation
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/stms

# Create __init__.py files agar Python modules terbaca dengan benar
RUN touch /app/stms/__init__.py && \
    touch /app/stms/routers/__init__.py

# Expose FastAPI port
EXPOSE 8000

# Health check validates the backend API is reachable
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health').read()" || exit 1

# Run FastAPI server dengan Uvicorn
# - host 0.0.0.0: listen pada semua interface
# - port 8000: standard FastAPI port
# - reload: auto-reload saat code berubah (development only, disable di production)
CMD ["uvicorn", "stms.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]