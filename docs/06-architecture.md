# HI Gallery — Technical Architecture

## Architecture
Use a **Modular Monolith** for the MVP.

```text
React Web Client
      |
      | REST / HTTPS, JSON
      v
Python + FastAPI
      |
      +---- PostgreSQL
      |
      +---- Future AI/Search integrations
```

Do not introduce microservices, Kafka, Kubernetes, or Elasticsearch for the MVP.

## Stack

### Backend
- Python 3.12+
- FastAPI for HTTP APIs and OpenAPI documentation
- Pydantic for request/response validation and settings
- SQLAlchemy 2.x for database access
- Alembic for schema migrations
- PostgreSQL
- pytest for automated tests
- Python virtual environment and `requirements.txt` for dependency management initially

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui

### Infrastructure
- Docker
- Docker Compose
- Git and CI/CD when configured

## Backend Structure
Use a `backend/app/` package. Organize business capabilities as modules and keep API, service, model, schema, and repository responsibilities clear without adding unnecessary abstraction.

```text
backend/
├── app/
│   ├── main.py
│   ├── core/          # settings, security, shared configuration
│   ├── db/            # SQLAlchemy setup and database session
│   ├── modules/
│   │   ├── auth/
│   │   ├── buyer/
│   │   ├── seller/
│   │   ├── admin/
│   │   ├── products/
│   │   ├── categories/
│   │   ├── cart/
│   │   ├── orders/
│   │   ├── payments/
│   │   └── reviews/
│   └── shared/
├── tests/
├── alembic/
├── alembic.ini
├── requirements.txt
└── Dockerfile
```

Within each module, use FastAPI routers for HTTP endpoints, Pydantic schemas for API contracts, services for business logic, and SQLAlchemy models/repositories for persistence where useful. Keep routers thin. Avoid creating layers that do not add value.

## Database
PostgreSQL is the transactional source of truth. Alembic manages schema migrations. The initial migration must match `docs/04-database-schema.sql`; do not silently redesign the documented schema. If the SQL schema conflicts with another requirement, report the conflict before changing it.

Use UUID primary keys as specified by the database schema. Keep database credentials in environment variables and never commit secrets.

## API
Use `/api/v1` as the API prefix. Return JSON and use UUID identifiers and ISO-8601 timestamps. FastAPI should expose its OpenAPI schema and interactive API docs in development. Follow `docs/05-api-specification.md` for endpoint intent and authorization requirements.

## Frontend
One React app contains:
- Buyer storefront
- Seller Studio/dashboard
- Admin Console

Suggested route groups: `/`, `/browse`, `/products/:id`, `/cart`, `/checkout`, `/orders`, `/seller/*`, `/admin/*`.

Use reusable design-system components. Do not put business rules or authorization decisions in UI components.

## Authentication and Authorization
Implement authentication with FastAPI-compatible, well-maintained libraries and secure password hashing. Never store plaintext passwords or hard-code secrets. Choose and document the session/token approach before implementing authentication. Enforce authorization on the backend; the frontend is not a security boundary. Sellers may access only their own products and SellerOrders; buyers may access only their own cart/orders and eligible reviews; admin endpoints require an admin role.

## AI
AI/search is a future enhancement, not an MVP dependency. AI output is enrichment or a suggestion; PostgreSQL remains the source of truth. Do not add AI integrations until core marketplace flows work.

## Scalability
Start with one backend deployment. Split modules only when there is a concrete scaling, deployment, ownership, or performance reason.

## Configuration
Use environment-based settings for database connection details, authentication secrets, payment-provider credentials, and future AI credentials. Provide a safe local `.env.example` if needed, but never commit real secrets.

## Testing
Use pytest for unit tests and API/integration tests for critical backend flows. Add frontend component/E2E tests for important user and purchase flows as the app develops. Tests must not depend on production credentials or services.

## Rules
Keep API routers thin, put business rules in services, validate input/output with Pydantic schemas, enforce authorization server-side, use Alembic migrations, and avoid premature infrastructure. Make incremental changes and run relevant tests after each implementation phase.
