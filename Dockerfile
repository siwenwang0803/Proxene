FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy poetry files
COPY pyproject.toml ./
COPY poetry.lock* ./

# Install poetry and dependencies
RUN pip install --no-cache-dir poetry==1.7.1 && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-interaction --no-ansi

# Copy application code
COPY proxene ./proxene
COPY run.py ./

# Create directories
RUN mkdir -p policies logs

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "run.py"]