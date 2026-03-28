FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY . .
RUN chmod +x entrypoint.sh

RUN adduser --disabled-password --gecos "" appuser && \
    mkdir -p /var/uploads && chown appuser:appuser /var/uploads
USER appuser

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
