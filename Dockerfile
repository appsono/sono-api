FROM python:3.10-slim

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/core/keys
COPY app/core/keys/public_key.pem /app/core/keys/

COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r /usr/src/app/requirements.txt

COPY ./app /usr/src/app/
COPY ./alembic /usr/src/app/alembic
COPY ./alembic.ini /usr/src/app/alembic.ini

EXPOSE 8000

# CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]