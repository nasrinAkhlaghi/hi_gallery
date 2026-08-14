# HI Gallery — Technical Architecture

## Architecture
Use a **Modular Monolith** for the MVP.

```text
React Web Client
      |
      | REST / HTTPS
      v
Java 17 + Spring Boot
      |
      +---- PostgreSQL
      |
      +---- Future AI/Search
```

Do not introduce microservices, Kafka, Kubernetes, or Elasticsearch for the MVP.

## Stack

### Backend
- Java 17
- Spring Boot
- Spring Security
- Spring Data JPA/Hibernate
- Flyway
- PostgreSQL
- Maven

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui

### Infrastructure
- Docker
- Docker Compose
- Git
- CI/CD

## Backend Modules
```text
com.higallery
├── auth
├── buyer
├── seller
├── admin
├── product
├── category
├── cart
├── order
├── payment
├── review
└── shared
```

Prefer module-local controller/service/repository/domain/dto boundaries.

## Database
PostgreSQL is the transactional source of truth. Flyway manages migrations. Runtime migration must remain consistent with `docs/04-database-schema.sql`.

## Frontend
One React app contains:
- Buyer
- Seller Studio
- Admin Console

Suggested route groups:
`/`, `/browse`, `/products/:id`, `/cart`, `/checkout`, `/orders`, `/seller/*`, `/admin/*`.

Use reusable design-system components. Do not put business rules in UI components.

## Authentication
Use Spring Security. Never store plaintext passwords. Use secure session/token handling. Frontend is not a security boundary.

## AI
Future AI/Search is adjacent to the core transactional application. AI output is enrichment/suggestion; PostgreSQL remains source of truth.

## Scalability
Start with one backend deployment. Split modules only when there is a concrete scaling, deployment, ownership, or performance reason.

## Configuration
Use environment variables for DB credentials, authentication secrets, external provider credentials, and AI credentials. Never commit secrets.

## Testing
Unit tests for business logic; integration/API tests for critical backend flows; component/E2E tests for important frontend and purchase flows.

## Rules
Keep controllers thin, use services for business logic, use DTOs for APIs, enforce backend authorization, and avoid premature infrastructure.
