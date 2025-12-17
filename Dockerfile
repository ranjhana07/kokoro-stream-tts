FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng libespeak-ng1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY pyproject.toml README.md gunicorn.conf.py ./
COPY src ./src
RUN pip install --no-deps .

RUN useradd --create-home app \
    && mkdir -p /app/output /app/models \
    && chown -R app /app
USER app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"

CMD ["gunicorn", "-c", "gunicorn.conf.py", "kokoro_stream.wsgi:app"]
