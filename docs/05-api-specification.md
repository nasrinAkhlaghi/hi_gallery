# HI Gallery — API Specification

Base URL: `/api/v1`
Format: JSON, UUID identifiers, ISO-8601 timestamps.

## Authentication
- POST `/auth/register`
- POST `/auth/register/seller`
- POST `/auth/login`
- POST `/auth/logout`
- GET `/auth/csrf`
- POST `/auth/refresh`
- GET `/auth/me`

All paths below are under `/api/v1`. State-changing cookie-authenticated requests require the `X-CSRF-Token` header and the matching `hi_gallery_csrf` cookie obtained from `GET /auth/csrf`. Send requests with browser credentials enabled. A present `Origin` header must match `CORS_ALLOWED_ORIGINS`.

### Registration

`POST /auth/register` accepts a buyer registration:

```json
{"email":"buyer@example.com","password":"a-password-of-at-least-12-characters","display_name":"Buyer Name"}
```

`POST /auth/register/seller` accepts:

```json
{"email":"maker@example.com","password":"a-password-of-at-least-12-characters","shop_name":"Clay Studio","description":"Optional shop description"}
```

Email is trimmed and case-normalized. Password length is 12–128 characters. Unknown fields are rejected. Seller registration creates only a SELLER profile in `DRAFT`; it does not submit an application. Registration never accepts a role field or creates an ADMIN. Both endpoints return `201` and the current-user shape below. They do not return tokens or automatically sign the user in. Duplicate emails return `409 EMAIL_ALREADY_REGISTERED`.

### Login and cookies

`POST /auth/login` accepts `{"email":"buyer@example.com","password":"…"}`. On success it returns the current-user response and sets:

- `hi_gallery_access`: signed access JWT, 15 minutes, HttpOnly, Path `/api/v1`.
- `hi_gallery_refresh`: opaque refresh credential, 7 days, HttpOnly, Path `/api/v1/auth`.
- `hi_gallery_csrf`: signed double-submit value, readable by JavaScript, Path `/api/v1`.

All cookies use `SameSite=Lax`, omit the Domain attribute, and set `Secure` in production. In local HTTP development, `Secure` is off. Invalid credentials return the same `401 INVALID_CREDENTIALS` response for unknown email and incorrect password. Authentication responses use `Cache-Control: no-store`.

### CSRF, refresh, logout

`GET /auth/csrf` returns `{"csrf_token":"…"}` and sets the matching CSRF cookie. Keep the returned value in memory and send it as `X-CSRF-Token` for every mutation. After login or refresh, call this endpoint again; the CSRF value is bound to the access-token ID when the access cookie is present, and falls back to the current refresh-token hash when no access cookie is sent. This keeps the value usable on seller API paths while preserving the refresh cookie's narrow `/api/v1/auth` path. The backend validates the cookie/header equality, signature, binding, and request origin where supplied.

`POST /auth/refresh` has no JSON body. It rotates the refresh cookie, creates a new access JWT, and returns the current-user response. The server stores only a SHA-256 hash of each opaque refresh token. Concurrent refresh attempts are serialized with a row lock; a competing in-flight attempt receives `409 REFRESH_IN_PROGRESS` and must retry only after obtaining current cookie/CSRF state. Reuse of a consumed token revokes the whole token family and returns `401 REFRESH_TOKEN_INVALID`.

`POST /auth/logout` has no JSON body and returns `204`. It revokes the presented refresh token; if the token was already rotated, it revokes its family. Repeating logout is safe. It clears the access, refresh, and CSRF cookies. Because access JWTs are stateless, logout or family revocation does not invalidate an already issued access JWT immediately; it may remain usable for up to 15 minutes, subject to the account's current ACTIVE state and role/profile checks.

### Current user

`GET /auth/me` requires a valid access cookie and returns only public account/authorization fields:

```json
{"id":"account-uuid","email":"user@example.com","roles":["BUYER"],"seller_status":null}
```

Roles are derived from the existing Buyer, Seller, and Admin profile relationships. `seller_status` is null without a seller profile; new sellers report `DRAFT`. Password hashes, token values, and security metadata are never included.

### Refresh-token retention

The migration creates `refresh_tokens` with UUID identity/account/family references, a unique token hash, creation/expiry/revocation timestamps, a replacement-token link, and reuse-detection timestamp. No plaintext refresh token is stored. Run a dry run with `python -m app.modules.auth.cleanup_refresh_tokens --dry-run` from `backend/`, then run `python -m app.modules.auth.cleanup_refresh_tokens` periodically through an external scheduler. The command deletes rows in transactions of at most 500 rows by default (configurable up to 5,000) when `expires_at` is more than 30 days in the past; it never deletes an unexpired token. Each batch commits separately, so runs are repeatable and hold locks only for a bounded batch. Reuse detection is retained for 30 days after a token expires; a token replay after that window cannot be associated with its former family once its row is removed. No scheduler is installed by the application.

## Buyer
- GET `/products`
- GET `/products/{productId}`
- GET `/categories`
- GET `/categories/{categoryId}/products`
- GET `/cart`
- POST `/cart/items`
- PATCH `/cart/items/{itemId}`
- DELETE `/cart/items/{itemId}`
- POST `/checkout`
- GET `/orders`
- GET `/orders/{orderId}`
- POST `/orders/{orderId}/reviews`

## Seller
- GET `/seller/profile`
- PATCH `/seller/profile`
- GET `/seller/application`
- POST `/seller/application/submit`
- GET `/seller/dashboard`
- GET `/seller/products`
- POST `/seller/products`
- GET `/seller/products/{productId}`
- PUT `/seller/products/{productId}`
- DELETE `/seller/products/{productId}`
- POST `/seller/products/{productId}/images`
- DELETE `/seller/products/{productId}/images/{imageId}`
- GET `/seller/orders`
- GET `/seller/orders/{sellerOrderId}`
- PATCH `/seller/orders/{sellerOrderId}/status`

### Seller onboarding (Phase 4.1)

All endpoints require an authenticated SELLER profile. State-changing requests use the documented CSRF cookie/header and Origin checks. Requests are scoped to the authenticated account; they never accept seller IDs or actor IDs from the client.

`GET /seller/profile` returns `{ "id", "shop_name", "description", "logo_url", "status", "created_at", "updated_at" }` for the caller's seller profile.

`PATCH /seller/profile` accepts only supplied editable fields from this set:

```json
{"shop_name":"Clay Studio","description":"Optional description","logo_url":"https://example.com/logo.png"}
```

`shop_name` must be nonblank and at most 150 characters. `description` is optional and at most 10,000 characters. `logo_url` is optional, at most 2,048 characters, and if present must be an absolute HTTP(S) URL. Unknown fields (including status, account and audit fields) are rejected. Editing is allowed only in `DRAFT`; a suspended seller receives `403`, and other non-draft profile edits receive `409`.

`GET /seller/application` returns `{ "status", "can_edit", "can_submit" }`. During Phase 4.1 both flags are true only for `DRAFT`.

`POST /seller/application/submit` accepts an empty body. It atomically changes `DRAFT` to `PENDING`, adds a `DRAFT` → `PENDING` seller lifecycle audit event, and returns the application status. Only a DRAFT can be submitted; duplicate or concurrent submissions return `409 INVALID_APPLICATION_TRANSITION`. Pending sellers may read profile and status but cannot edit or submit again. Rejected-seller editing/resubmission is planned for a later phase; Admin review and decision endpoints are not implemented in Phase 4.1.

The seller status history is append-only. Phase 4.1 records seller registration (`NULL` → `DRAFT`) and application submission (`DRAFT` → `PENDING`) with actor type `SELLER` and identity derived from the authenticated account. The migration does not fabricate events for sellers that existed before it; historical PENDING rows remain PENDING and have no synthetic history.

## Admin
- GET `/admin/dashboard`
- GET `/admin/sellers`
- GET `/admin/sellers/{sellerId}`
- POST `/admin/sellers/{sellerId}/approve`
- POST `/admin/sellers/{sellerId}/reject`
- POST `/admin/sellers/{sellerId}/suspend`
- GET `/admin/buyers`
- GET `/admin/products`
- GET `/admin/orders`
- GET `/admin/reviews`

## Authorization
Backend must enforce ownership. Seller can access only own products/SellerOrders. Buyer can access only own cart/orders and eligible reviews. Admin can access admin APIs.

## Errors
Use:
```json
{
  "code": "RESOURCE_NOT_FOUND",
  "message": "Product not found",
  "details": null,
  "timestamp": "2026-08-14T12:00:00Z"
}
```

Status codes: 200, 201, 204, 400, 401, 403, 404, 409, 422, 500.

## Rules
Use DTOs rather than exposing persistence entities. Validate requests. Enforce authorization server-side. Use pagination on collection endpoints; default page 0/size 20 and enforce a maximum size.
