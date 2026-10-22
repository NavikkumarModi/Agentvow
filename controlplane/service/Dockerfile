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
CMD ["python", "-m", "uvicorn", "controlplane.service.asgi:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
