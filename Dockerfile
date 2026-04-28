FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
COPY pyproject.toml .
COPY bankpromos bankpromos
COPY data data

RUN mkdir -p /app/data

RUN pip install --no-cache-dir -r requirements.txt

RUN pip install --no-cache-dir playwright && \
    playwright install --with-deps chromium

ENV BANKPROMOS_DB_PATH=/app/data/bankpromos.db
ENV BANKPROMOS_DISABLE_LIVE_SCRAPING=true
ENV BANKPROMOS_CACHE_HOURS=12

RUN echo "Build $(date -u)" > /build.txt

EXPOSE 8000

CMD sh -c "uvicorn bankpromos.api:app --host 0.0.0.0 --port ${PORT:-8000}"