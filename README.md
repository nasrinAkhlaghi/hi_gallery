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

### Start the frontend

In a separate terminal, from the repository root:

```sh
cd frontend
npm install
npm run dev
```

Vite prints the local URL when it starts (normally <http://localhost:5173>).

See `docs/06-architecture.md` for the technical decisions and module boundaries.
