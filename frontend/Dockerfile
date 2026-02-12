FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Use gunicorn for production
RUN pip install gunicorn

# Create a non-privileged user
ARG UID=10001
RUN adduser --disabled-password --gecos "" --shell "/sbin/nologin" --uid "${UID}" appuser

# Switch to non-privileged user
USER appuser

# Expose port
EXPOSE 3000

# Production command
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "app:app"]
