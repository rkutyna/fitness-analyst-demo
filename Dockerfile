# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt \
 && find /opt/venv -type d -name __pycache__ -prune -exec rm -rf {} + \
 && rm -rf /opt/venv/lib/python3.11/site-packages/pip* \
           /opt/venv/lib/python3.11/site-packages/setuptools* \
           /opt/venv/lib/python3.11/site-packages/_distutils_hack

FROM python:3.11-slim
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    BUNDLE_DIR=/app/bundle \
    WEB_DIR=/app/web
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY app/ app/
COPY web/ web/
COPY bundle/ bundle/
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
