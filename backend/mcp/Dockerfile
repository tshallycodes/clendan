FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY clendan_mcp/ ./clendan_mcp/

RUN pip install --no-cache-dir -e ".[http]"

EXPOSE 8080

CMD ["uvicorn", "clendan_mcp.http_server:app", "--host", "0.0.0.0", "--port", "8080"]
