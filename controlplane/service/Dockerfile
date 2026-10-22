# Build from the repository root: docker build -f controlplane/service/Dockerfile -t agentvow-controlplane .
FROM python:3.12-slim
RUN useradd --create-home --uid 10001 cp && mkdir /data && chown cp /data
WORKDIR /app
COPY controlplane/service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY agentvow /app/agentvow
COPY controlplane /app/controlplane
USER cp
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
VOLUME /data
EXPOSE 8080
# One process: SQLite with an in-process lock. Scale vertically; a second replica needs a different store.
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request,sys;sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3).read()==b'ok' else 1)"
CMD ["python", "-m", "uvicorn", "--factory", "controlplane.service.asgi:create_app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--limit-concurrency", "64", "--timeout-keep-alive", "5"]
