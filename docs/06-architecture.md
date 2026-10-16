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
Authentication uses Argon2id password hashes, 15-minute HS256 access JWTs, and seven-day database-backed opaque refresh tokens. Access tokens are signed with an explicit algorithm, issuer, audience, subject, token ID, session-family ID, and access token type. JWT and CSRF signing keys are required environment settings (minimum 32 bytes); no secret is hard-coded.

The access JWT and refresh credential are held only in separate HttpOnly cookies. Both use `SameSite=Lax`, narrow paths, no Domain attribute, and `Secure` in production. The readable CSRF cookie contains a signed double-submit value bound to the current refresh-token hash or access token ID; the frontend also keeps the value in memory and sends `X-CSRF-Token` for state-changing requests. Origin checks and credentialed CORS use the explicit `CORS_ALLOWED_ORIGINS` allowlist. Frontend code never stores authentication tokens in localStorage/sessionStorage.

Refresh credentials are cryptographically random opaque values. PostgreSQL stores only SHA-256 hashes in `refresh_tokens`, grouped by a UUID family. Each successful refresh consumes one token and links it to its successor in one transaction. Row locking with `NOWAIT` allows at most one concurrent refresh to win; a competing request gets `409 REFRESH_IN_PROGRESS`. Presenting a consumed token after a committed rotation is treated as reuse and revokes the full family. Logout revokes the current token or family and clears cookies. Access JWTs are stateless, so logout/family revocation does not immediately revoke already issued access JWTs; account status and roles are still loaded from PostgreSQL on protected requests, and the token expires within 15 minutes.

Roles come only from the existing Buyer, Seller, and Admin profile relationships. Public registration can create Buyer or PENDING Seller profiles only. Reusable FastAPI dependencies return 401 for absent/invalid authentication and 403 for missing roles or a seller who is not ACTIVE. Frontend route guards are only a user-experience feature; authorization must also be enforced by backend route dependencies. No general session table, Redis, refresh-token cleanup scheduler, or business endpoints are introduced. Operators can run `python -m app.modules.auth.cleanup_refresh_tokens --dry-run` from `backend/` to count eligible rows, then schedule `python -m app.modules.auth.cleanup_refresh_tokens` externally. Cleanup deletes at most 500 rows per transaction by default (up to 5,000 when explicitly configured) after `expires_at` is more than 30 days old, preserving a 30-day post-expiry reuse-detection window and never deleting an unexpired token. This bounds old records after expiry; replays later than the retention window cannot be associated with their former family.

### Current security limitations

- There is no login/register rate limiting, MFA, email verification, password reset, or account recovery flow in this phase.
- Access JWTs remain valid until their 15-minute expiry after logout or family revocation; there is no access-token denylist.
- Signing-key rotation is an operator-managed deployment action and invalidates outstanding tokens signed with the previous key.
- CSRF protection does not defend against same-origin script injection; the CSRF value is intentionally available to frontend JavaScript, while auth tokens remain HttpOnly.
- The refresh-row cleanup command is operator-scheduled, not run by the application. Reuse detection is limited to the 30-day post-expiry retention window.
- PostgreSQL lock behavior is covered by an opt-in test requiring a separate isolated database; that integration test is skipped in the default test run.

## AI
AI/search is a future enhancement, not an MVP dependency. AI output is enrichment or a suggestion; PostgreSQL remains the source of truth. Do not add AI integrations until core marketplace flows work.

## Scalability
Start with one backend deployment. Split modules only when there is a concrete scaling, deployment, ownership, or performance reason.

## Configuration
Use environment-based settings for database connection details and auth/CSRF signing secrets. `DATABASE_URL`, `JWT_SIGNING_KEY`, and `CSRF_SIGNING_KEY` are required. Also configure `ENVIRONMENT`, `AUTH_ISSUER`, `AUTH_AUDIENCE`, `CORS_ALLOWED_ORIGINS`, and frontend `VITE_API_BASE_URL`. Local development uses explicit HTTP localhost origins and non-Secure cookies; production must use HTTPS, `ENVIRONMENT=production`, high-entropy independent signing keys, and exact trusted origins. `.env.example` contains placeholders only; never commit real secrets.

Install the backend dependencies, configure the root `.env`, and run `alembic upgrade head` from `backend/` to create the `0002_refresh_tokens` table after confirming the target database. Tests use isolated SQLite fixtures by default. The PostgreSQL concurrency test only runs when `TEST_DATABASE_URL` points to a separate disposable database and `TEST_DATABASE_ISOLATED=1` is explicitly set; it never uses `DATABASE_URL`.

## Testing
Use pytest for unit tests and API/integration tests for critical backend flows. Add frontend component/E2E tests for important user and purchase flows as the app develops. Tests must not depend on production credentials or services.

## Rules
Keep API routers thin, put business rules in services, validate input/output with Pydantic schemas, enforce authorization server-side, use Alembic migrations, and avoid premature infrastructure. Make incremental changes and run relevant tests after each implementation phase.
