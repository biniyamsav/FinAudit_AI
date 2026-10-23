## Setup

```
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `DATABASE_URL` to your local PostgreSQL database.

## Database

Create the database `financial_audit_db`, then apply migrations:

```
python -m alembic upgrade head
```

## Tests

Tests run against a separate database named `audit_test` on the same server.
Create it once (`CREATE DATABASE audit_test;`). Pytest migrates it automatically.

```
python -m pytest -q
```