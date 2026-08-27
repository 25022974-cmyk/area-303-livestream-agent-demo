FROM python:3.11-slim

WORKDIR /app

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY model_bibica /app/model_bibica
COPY server /app/server

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

WORKDIR /app
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
