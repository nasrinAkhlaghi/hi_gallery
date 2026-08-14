# HI Gallery

HI Gallery (Human Intelligence Gallery) is a handmade marketplace connecting independent creators with buyers.

## Stack
- Java 17
- Spring Boot
- PostgreSQL
- Flyway
- React
- TypeScript
- Vite
- Tailwind CSS
- shadcn/ui
- Docker

## Architecture
MVP uses a modular monolith.

## Specification
Read every file under `docs/` before implementing features. They define product requirements, domain model, user flows, database schema, API contracts, architecture, and UI requirements.

Do not invent undefined business rules. Ask when specifications conflict. Implement incrementally.

## Core Flow
Seller registration → Admin approval → Product creation → Buyer discovery → Cart → Checkout → Payment → Order → Seller fulfillment → Buyer review.

AI/search enhancements are planned for later phases.
