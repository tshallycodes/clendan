FROM python:3.12-slim

WORKDIR /app

RUN pip install poetry==1.8.2 && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root --only main

COPY . .

RUN poetry run prisma generate

EXPOSE 8000

# PORT env var is set by Railway; falls back to 8000 for local Docker
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# To run the arq background worker (set as startCommand in railway.worker.toml):
# CMD ["python", "-m", "arq", "app.worker.WorkerSettings"]
