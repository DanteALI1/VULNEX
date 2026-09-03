FROM python:3.12-slim-bookworm
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn cryptography pydantic
COPY license_server /app
EXPOSE 8090
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
