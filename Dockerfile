FROM python:3.11-slim

LABEL maintainer="Oidasheim" \
      description="OIDASHEIM BEAT SYNC VIDEO EDITOR — Docker Image" \
      version="1.0.0"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY requirements.txt .
COPY setup.py .
COPY pyproject.toml .
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir gunicorn

# Create data volumes
RUN mkdir -p /app/logs /app/data /app/output

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import main; print('OK')" || exit 1

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LOG_LEVEL=INFO

# Default command
CMD ["python", "main.py"]

# Volume mount points
VOLUME ["/app/logs", "/app/data", "/app/output"]

# Exposed ports (if using Flask API)
EXPOSE 5000
