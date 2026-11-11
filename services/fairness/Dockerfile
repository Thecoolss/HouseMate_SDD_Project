FROM python:3.12.16-slim-bookworm


# DATA_DIR: only used when DATABASE_URL is unset (docker run without compose). /app is
# read-only for appuser, so the fallback SQLite file goes in /tmp and is lost on removal.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=5001 \
    DATA_DIR=/tmp/data

WORKDIR /app


RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py config.py ./
COPY app/ ./app/

USER appuser

EXPOSE 5001

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PORT\"]}/health', timeout=2)" || exit 1


CMD exec gunicorn --bind 0.0.0.0:${PORT} "app:create_app()"
