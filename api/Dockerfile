# Built with repo-root context (see infra/docker-compose.yml: `context: ..`,
# `dockerfile: api/Dockerfile`) because /chat imports the sibling agent/
# package -- api/-only context can't see it.
FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt ./api/requirements.txt
COPY agent/requirements.txt ./agent/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt -r agent/requirements.txt

COPY api/ ./api
COPY agent/ ./agent

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
