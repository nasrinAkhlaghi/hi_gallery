# HI Gallery

HI Gallery (Human Intelligence Gallery) is a handmade marketplace connecting independent creators with buyers.

## Technology Stack

### Backend
- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Pydantic
- Alembic for database migrations
- PostgreSQL
- pytest

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui

### Infrastructure
- Docker
- Docker Compose

## Architecture
The MVP uses a modular monolith. The backend is one FastAPI application organized into business modules; the frontend is one React application with Buyer, Seller Studio, and Admin Console route groups.

## Specification
Read every file under `docs/` before implementing features. They define product requirements, domain model, user flows, database schema, API contracts, architecture, and UI requirements.

Do not invent undefined business rules. Ask when specifications conflict. Implement incrementally.

## Core Flow
Seller registration → Admin approval → Product creation → Buyer discovery → Cart → Checkout → Payment → Order → Seller fulfillment → Buyer review.

AI/search enhancements are planned for later phases and are not part of the MVP.

## Local Development

### Prerequisites

- Python 3.12 or newer
- Node.js LTS (with npm)
- Docker Desktop with Docker Compose

### Configure the environment

Copy `.env.example` to `.env` in the repository root. The included values are for local development only; change them if they conflict with your environment. Keep `.env` private.

```powershell
Copy-Item .env.example .env
```

Set independent random signing keys before starting the API. Each key must contain at least 32 bytes; keep them private and stable across restarts:

```powershell
python -c "import secrets; print('JWT_SIGNING_KEY=' + secrets.token_urlsafe(48)); print('CSRF_SIGNING_KEY=' + secrets.token_urlsafe(48))"
```

Copy the two generated values into `.env`. For production, set `ENVIRONMENT=production`, use HTTPS, set `DATABASE_URL`, and list the exact frontend origins in `CORS_ALLOWED_ORIGINS`.

On macOS or Linux, use `cp .env.example .env` instead.

### Start PostgreSQL

From the repository root, start the database container:

```sh
docker compose up -d postgres
```

Check its status with `docker compose ps`. The database data is kept in a Docker volume.

### Set up and run the backend

Create a virtual environment inside `backend/`:

```powershell
cd backend
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
```

On macOS or Linux, create it with `python3 -m venv .venv` and activate it with `source .venv/bin/activate`.

Install dependencies and apply the database migration:

```sh
python -m pip install -r requirements.txt
alembic upgrade head
```

Start FastAPI with reload enabled:

```sh
uvicorn app.main:app --reload
```

The health endpoint is at <http://127.0.0.1:8000/health>; interactive API docs are at <http://127.0.0.1:8000/docs>.

Run the backend tests from `backend/` with:

```sh
pytest
```

Auth uses a 15-minute signed access JWT and a rotating seven-day opaque refresh token in separate HttpOnly cookies. See [Authentication API](docs/05-api-specification.md#authentication) and [Authentication architecture](docs/06-architecture.md#authentication-and-authorization). The new refresh-token table is migration `0002_refresh_tokens`; after reviewing the target database, apply it from `backend/` with `alembic upgrade head`. Do not point test suites at a shared or production database.

For routine refresh-token cleanup, run a dry run from `backend/` with `python -m app.modules.auth.cleanup_refresh_tokens --dry-run`, then schedule `python -m app.modules.auth.cleanup_refresh_tokens` through an external scheduler. It deletes expired records in bounded batches after a 30-day post-expiry retention period; no scheduler is installed by the application.

### Start the frontend

In a separate terminal, from the repository root:

```sh
cd frontend
npm install
npm run dev
```

The frontend sends credentialed requests to `VITE_API_BASE_URL` (default local value: `http://localhost:8000/api/v1`). Authentication cookies are never read by JavaScript or copied into browser storage. Start the API and frontend on the explicit local origins listed in `CORS_ALLOWED_ORIGINS`.

Run the frontend checks from `frontend/` with `npm test` and `npm run build`.

Vite prints the local URL when it starts (normally <http://localhost:5173>).

See `docs/06-architecture.md` for the technical decisions and module boundaries.
