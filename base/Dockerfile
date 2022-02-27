FROM python:3-alpine

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN apk add --no-cache gcc musl-dev libpq postgresql-dev && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    apk del --purge gcc musl-dev postgresql-dev

COPY lib/*/*.py ./
