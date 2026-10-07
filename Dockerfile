FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml ./
COPY src/ src/
COPY static/ static/
COPY data/ data/
RUN uv pip install --system --no-cache .

EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --app-dir src --host 0.0.0.0 --port ${PORT:-8000}"]
