# ===== Stage 1: Tailwind builder =====
FROM node:20-alpine AS tailwind_builder
WORKDIR /build
COPY package.json tailwind.config.js postcss.config.js ./
RUN npm install
COPY src/static/src/css ./src/static/src/css
COPY src/templates ./src/templates
RUN npx tailwindcss -i ./src/static/src/css/app.css -o ./src/static/css/app.css --minify

# ===== Stage 2: Python runtime =====
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /code

# System deps for psycopg & cryptography
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e ".[dev]"

# Copy app source
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

# Copy compiled CSS from tailwind stage
COPY --from=tailwind_builder /build/src/static/css/app.css ./src/static/css/app.css

# Create temp dir for exports
RUN mkdir -p /code/tmp/exports

# Non-root user
RUN groupadd -r app && useradd -r -g app -d /code app && chown -R app:app /code
USER app

EXPOSE 7788

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:7788/healthz || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "7788", "--proxy-headers", "--forwarded-allow-ips=*"]
