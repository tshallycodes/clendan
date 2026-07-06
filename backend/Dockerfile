FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==2.4.1 && \
    poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-interaction --no-ansi --no-root --only main

COPY . .

RUN poetry run prisma generate

EXPOSE 8000

# PORT env var is set by Railway; falls back to 8000 for local Docker
CMD ["sh", "-c", "prisma db push --skip-generate && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

# To run the arq background worker (separate Railway service):
# CMD ["python", "run_tool.py", "app.tool.ToolSettings"]
