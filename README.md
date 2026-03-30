# Movies ETL Pipeline

A fault-tolerant ETL (Extract, Transform, Load) pipeline that migrates movie data from SQLite through PostgreSQL into Elasticsearch, backed by a Django admin panel and served behind Nginx. The entire stack runs in Docker Compose.

## Architecture

### Data flow

```
SQLite ─-> PostgreSQL ─-> Elasticsearch
                │
        Django Admin & REST API
```

1. **SQLite -> PostgreSQL** — the `move_data` container reads `db.sqlite` and inserts rows into the `content` schema (genres, persons, film works, and their many-to-many relations).
2. **PostgreSQL -> Elasticsearch** — the `etl` container polls PostgreSQL in a loop, picks up any rows whose `updated_at` timestamp exceeds the last recorded state, transforms them with Pydantic models, and indexes them into Elasticsearch.

## Project Structure

```
.
├── docker-compose.yaml          # full stack definition
├── Dockerfile                   # Django admin image
├── .env.template                # env var template
├── db/
│   └── initdb.sql               # creates the `content` schema in PostgreSQL
├── movies_admin/                # Django project
│   ├── config/                  # Django settings, WSGI, URLs
│   ├── movies/                  # models, admin, migrations
│   ├── api/v1/                  # REST API
│   └── requirements.txt
├── sqlite_to_postgres/          # SQLite -> PostgreSQL migration
│   ├── db.sqlite                # seed database with movie data
│   ├── db_classes.py            # dataclasses matching SQLite tables
│   ├── sqlite_loader.py         # reads all tables from SQLite
│   ├── postgres_saver.py        # inserts data into PostgreSQL
│   ├── load_data.py             # entry point
│   └── Dockerfile
├── postgres_to_es/              # PostgreSQL -> Elasticsearch ETL
│   ├── config/                  # ES index schemas (movies, genres, persons)
│   ├── models.py                # Pydantic models for validation
│   ├── state.py                 # persistent state storage
│   ├── main.py                  # ETL entry point
│   ├── create_indexes.sh        # Creates ES indexes on startup
│   └── Dockerfile
├── src/                         # Nginx configuration
│   ├── nginx.conf
│   └── conf/site.conf
├── postman_etl.json             # Postman collection for API testing
└── .github/workflows/main.yml   # CI: builds and pushes Docker images
```

## Getting Started

### Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/whois-cat/ETL.git
   cd ETL
   ```

2. Create an `.env` file from the template and fill in the values in `.env`:

   ```bash
   cp .env.template .env
   ```

3. Start all services:

   ```bash
   docker-compose up --build
   ```

The startup sequence is:

1. PostgreSQL starts and creates the `content` schema.
2. Django runs migrations and launches Gunicorn on port 8000.
3. The `move_data` container loads seed data from SQLite into PostgreSQL.
4. Elasticsearch starts in single-node mode.
5. The ETL container creates indexes in Elasticsearch and begins continuous sync.
6. Nginx starts proxying requests on port 80.

### Accessing Services

| Service | URL |
|---|---|
| Django Admin | `http://localhost/admin/` |
| Movies API (list) | `http://localhost/api/v1/movies/` |
| Movies API (detail) | `http://localhost/api/v1/movies/<uuid>/` |
| Elasticsearch | `http://localhost:9200/` |

## CI/CD

A GitHub Actions workflow (`.github/workflows/main.yml`) builds and pushes three Docker images to Docker Hub on every push or PR to `main`:

- `lobart/yandex-admin` — Django admin
- `lobart/yandex-sqlite-to-postgres` — SQLite migration
- `lobart/yandex-etl:main` — ETL process

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `POSTGRES_DB` | PostgreSQL database name | `movies` |
| `POSTGRES_USER` | PostgreSQL user | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | — |
| `POSTGRES_HOST` | PostgreSQL host | `database` |
| `POSTGRES_PORT` | PostgreSQL port | `5432` |
| `SECRET_KEY` | Django secret key | — |
| `ES_HOST` | Elasticsearch host and port | `es:9200` |
| `BATCH_SIZE` | number of rows fetched per ETL batch | `100` |

## Tech Stack

- **Python 3.9** — Django 3.2, Pydantic, psycopg2, backoff, elasticsearch-py
- **PostgreSQL 13**
- **Elasticsearch 6.8**
- **Nginx 1.20**
- **Docker & Docker Compose**
- **Gunicorn** — WSGI server for Django
- **GitHub Actions** — CI pipeline
