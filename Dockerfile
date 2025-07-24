FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY proxene ./proxene
COPY run.py ./

# Create directories
RUN mkdir -p policies logs

# Expose port
EXPOSE 8080

# Run the application
CMD ["python", "run.py"]