# Sono API

Backend service for the Sono music platform ecosystem.

This API provides authentication, user management, audio uploads, collections
(playlists, albums, compilations), announcements, and admin functionality for
the Sono mobile app (Flutter) and Sono web app (Vue).

Built with **FastAPI**.

---

## Tech Stack

* Python
* FastAPI
* Pydantic
* Alembic (database migrations)
* JWT authentication
* Docker & Docker Compose
* MinIO (object storage)

---

## API Overview

* **Base URL (development):** `http://localhost:8000`
* **API prefix:** `/api/v1`
* **Authentication:** Bearer access tokens
* **Interactive API docs:**

  * Swagger UI: `/docs`
  * ReDoc: `/redoc`

---

## Project Structure

```text
.
├── alembic/                # Alembic migrations
├── app/                    # Application source
│   ├── core/               # Core utilities and shared logic
│   ├── routers/            # FastAPI routers (endpoints)
│   ├── tasks/              # Background / async tasks
│   ├── __init__.py
│   ├── crud.py             # Database CRUD operations
│   ├── database.py         # Database setup and session
│   ├── dependencies.py     # FastAPI dependencies
│   ├── main.py             # FastAPI entrypoint
│   ├── models.py           # Database models
│   └── schemas.py          # Pydantic schemas
├── scripts/                # Utility scripts
├── .env.example            # Environment variable template
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── requirements.txt
├── README.md
└── API_REFERENCE.md        # Full endpoint reference
```

---

## Application Entry Point

The FastAPI application is defined in:

```
app/main.py
```

This file initializes the app and registers all routers.

---

## Routers

All HTTP endpoints are defined in `app/routers/`.

Routers are responsible for:

* Request validation
* Authentication and dependencies
* Returning API responses

---

## Database

* Database configuration and session handling live in `app/database.py`
* Schema migrations are managed via Alembic in the `alembic/` directory

---

## Background Tasks

Background and async tasks live in:

```
app/tasks/
```

---

## Local Development

### 1. Configure environment

```bash
cp .env.example .env
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the API

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```
http://localhost:8000
```

---

## Docker

Run using Docker Compose:

```bash
docker-compose up --build
```

---

## Authentication

All protected endpoints require:

```http
Authorization: Bearer <access_token>
```

---

## API Reference

Full endpoint documentation is available in:

➡ **API_REFERENCE.md**

---

## Status

This API is under active development.

---

## License

Private / internal use for the Sono platform.