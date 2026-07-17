# NOTE: infra/docker-compose.yml builds this image with `context: ../api`,
# i.e. only the api/ directory is available as build context. /chat imports
# `agent.tools`, which lives in the sibling agent/ directory -- that import
# only resolves if agent/ is present in the image. See api/README.md
# "Known limitation" for how to fix this (repo-root build context, or
# vendoring agent/ into api/) without touching infra/docker-compose.yml.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./api

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
