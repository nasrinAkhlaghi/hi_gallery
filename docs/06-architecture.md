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
PostgreSQL is the transactional source of truth. Alembic manages additive schema migrations. `backend/alembic/schema.sql` is the frozen source used by `0001_initial_schema`; `docs/04-database-schema.sql` documents the current schema after subsequent migrations. Do not rewrite an applied migration's source to reflect later changes.

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

The access JWT and refresh credential are held only in separate HttpOnly cookies. Both use `SameSite=Lax`, narrow paths, no Domain attribute, and `Secure` in production. The readable CSRF cookie contains a signed double-submit value bound to the access-token ID when that cookie is present, falling back to the refresh-token hash when only the refresh cookie is sent. This supports state-changing requests outside `/api/v1/auth` without broadening the refresh cookie path. The frontend keeps the CSRF value in memory and sends `X-CSRF-Token`; backend checks still require cookie/header equality, signature, binding, and an allowed Origin when present. Credentialed CORS uses the explicit `CORS_ALLOWED_ORIGINS` allowlist. Frontend code never stores authentication tokens in localStorage/sessionStorage.

Refresh credentials are cryptographically random opaque values. PostgreSQL stores only SHA-256 hashes in `refresh_tokens`, grouped by a UUID family. Each successful refresh consumes one token and links it to its successor in one transaction. Row locking with `NOWAIT` allows at most one concurrent refresh to win; a competing request gets `409 REFRESH_IN_PROGRESS`. Presenting a consumed token after a committed rotation is treated as reuse and revokes the full family. Logout revokes the current token or family and clears cookies. Access JWTs are stateless, so logout/family revocation does not immediately revoke already issued access JWTs; account status and roles are still loaded from PostgreSQL on protected requests, and the token expires within 15 minutes.

Roles come only from the existing Buyer, Seller, and Admin profile relationships. Public registration can create Buyer or DRAFT Seller profiles only. ADMIN role derivation and review authorization require an Admin profile with `status = ACTIVE`; inactive Admin profiles do not authorize Admin routes. Reusable FastAPI dependencies return 401 for absent/invalid authentication and 403 for missing roles or a seller who is not ACTIVE. Frontend route guards are only a user-experience feature; authorization must also be enforced by backend route dependencies. No generic session table, Redis, or refresh-token cleanup scheduler is introduced. Operators can run `python -m app.modules.auth.cleanup_refresh_tokens --dry-run` from `backend/` to count eligible rows, then schedule `python -m app.modules.auth.cleanup_refresh_tokens` externally. Cleanup deletes at most 500 rows per transaction by default (up to 5,000 when explicitly configured) after `expires_at` is more than 30 days old, preserving a 30-day post-expiry reuse-detection window and never deleting an unexpired token. This bounds old records after expiry; replays later than the retention window cannot be associated with their former family.

### Seller onboarding (Phase 4.1)

New sellers start in `DRAFT`. They can read and update their own `shop_name`, optional `description`, and optional HTTP(S) `logo_url`, then explicitly submit the profile. Submission locks the seller row, changes only `DRAFT` to `PENDING`, and appends its audit event in the same PostgreSQL transaction. A database trigger rejects UPDATE, DELETE, and TRUNCATE against `seller_status_history`. Existing PENDING and other existing statuses are unchanged by migration `0003_seller_onboarding`; no synthetic audit events are added for pre-migration records. Profile/status reads are available to the authenticated seller, while editing/submission is restricted to DRAFT. Approved-only operations continue to require status ACTIVE.

### Admin seller review (Phase 4.2)

Admin review uses the existing Seller and append-only `seller_status_history` tables; there is no schema migration. The default queue lists only PENDING submitted applications, with status filtering and bounded pagination. Submission time is derived from the application-submitted audit event. Seller detail returns only review fields and ordered history; account email, tokens, password hashes, and actor account IDs are excluded. Admin actor display names are returned only for Admin review.

Approval (`PENDING` → `ACTIVE`) and rejection (`PENDING` → `REJECTED`) use a conditional database update that matches only the current PENDING status. The successful status update and audit insert commit in one transaction. Competing decisions serialize on the row update; one succeeds, while the other receives 409. Failed audit insertion rolls back the status update. Rejection requires a trimmed 1–2000 character reason. The authenticated Admin account supplies actor identity, and a seller cannot review their own application. The seller's application endpoint exposes the rejection reason from the latest rejection audit record only to that seller. Rejected-seller profile editing/resubmission and suspension remain unimplemented.

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

Install the backend dependencies, configure the root `.env`, and run `alembic upgrade head` from `backend/` after confirming the target database; this applies `0002_refresh_tokens` and `0003_seller_onboarding` after the original schema. Tests use isolated SQLite fixtures by default. PostgreSQL concurrency and migration compatibility tests only run when `TEST_DATABASE_URL` points to a separate disposable database and `TEST_DATABASE_ISOLATED=1` is explicitly set; they never target the configured development database.

## Testing
Use pytest for unit tests and API/integration tests for critical backend flows. Add frontend component/E2E tests for important user and purchase flows as the app develops. Tests must not depend on production credentials or services.

## Rules
Keep API routers thin, put business rules in services, validate input/output with Pydantic schemas, enforce authorization server-side, use Alembic migrations, and avoid premature infrastructure. Make incremental changes and run relevant tests after each implementation phase.
