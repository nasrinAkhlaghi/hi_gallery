# HI Gallery — API Specification

Base URL: `/api/v1`
Format: JSON, UUID identifiers, ISO-8601 timestamps.

## Storefront APIs (steps 1 and 2)

`GET/PATCH /seller/shop` is implemented for ACTIVE sellers. Public `/shops/{sellerId}`, `/shops/{sellerId}/products`, `/products`, `/products/{productId}` and `/categories/{categoryId}/products` are also implemented for signed-out and signed-in visitors. Request/response fields, search, pagination, authorization and public visibility are specified in [Storefront plan — API contracts](09-storefront-plan.md#planned-api-contracts). Existing onboarding `/seller/profile` contracts remain unchanged; ACTIVE seller presentation edits use the separate shop endpoint.

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
- GET `/shops/{sellerId}`
- GET `/shops/{sellerId}/products`
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

### Public shop and product discovery (storefront step 2)

All public GET endpoints are available without login and return only explicit public fields. Shops require both an ACTIVE seller and owning account; unknown/unavailable shops return `404 SHOP_NOT_FOUND`. Public products additionally require ACTIVE or SOLD_OUT status; all other product detail requests return `404 PRODUCT_NOT_FOUND`. The same eligibility applies before list pagination and total counting. Zero stock does not automatically change status; SOLD_OUT and zero-stock products remain visible.

`GET /shops/{sellerId}` returns `{id,shop_name,description,logo_url,category,theme_id}`. Primary category is null if absent or disabled. `GET /shops/{sellerId}/products` returns only that shop's visible products; an available empty shop returns 200 with an empty page.

All public product lists return `{items,total,page,page_size}` with zero-based pages, default size 20, sizes 1–100, and creation time descending then UUID. Product projection is `{id,name,description,category,price,stock,status,images,seller}`. Category has `{id,parent_id,name,slug}`, seller has only `{id,shop_name}`, images have `{id,url,sort_order}` sorted cover-first, and prices are decimal strings. No private account/application fields or fabricated ratings are included.

`GET /products` supports optional `q` (trimmed, maximum 200 characters, case-insensitive literal name substring) and `category_id` (exact category, without descendants). Search wildcards are treated literally; blank search adds no filter. Shop product lists support the same exact `category_id` filter. Well-formed filters with no matches return an empty page. Invalid query values/UUIDs return 422. `GET /categories/{categoryId}/products` requires an ACTIVE category or returns `404 CATEGORY_NOT_FOUND`. Disabling a category does not hide its published products from Browse or detail; it removes the category from active navigation and makes this dedicated category route unavailable.

These endpoints are implemented; their frontend pages remain placeholders until the next UI tasks. The complete field contracts and acceptance criteria are in [Storefront plan](09-storefront-plan.md).

## Seller
- GET `/seller/profile`
- PATCH `/seller/profile`
- GET `/seller/application`
- POST `/seller/application/submit`
- GET `/seller/shop`
- PATCH `/seller/shop`
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

After Phase 4.2, this response also includes `rejection_reason` for the authenticated seller's own `REJECTED` application, derived from its latest `APPLICATION_REJECTED` audit event. It is null for other statuses. Rejected sellers cannot edit or resubmit in this phase.

`POST /seller/application/submit` accepts an empty body. It atomically changes `DRAFT` to `PENDING`, adds a `DRAFT` → `PENDING` seller lifecycle audit event, and returns the application status. Only a DRAFT can be submitted; duplicate or concurrent submissions return `409 INVALID_APPLICATION_TRANSITION`. Pending sellers may read profile and status but cannot edit or submit again. Rejected-seller editing/resubmission is planned for a later phase; Admin review and decision endpoints are not implemented in Phase 4.1.

The seller status history is append-only. Phase 4.1 records seller registration (`NULL` → `DRAFT`) and application submission (`DRAFT` → `PENDING`) with actor type `SELLER` and identity derived from the authenticated account. The migration does not fabricate events for sellers that existed before it; historical PENDING rows remain PENDING and have no synthetic history.

### Shop settings (storefront step 1)

`GET /seller/shop` and `PATCH /seller/shop` require an authenticated ACTIVE account with an ACTIVE Seller profile. GET returns `{id,shop_name,description,logo_url,shop_category_id,theme_id,updated_at}` for the caller; private account/application fields are excluded.

PATCH requires the existing CSRF and Origin checks and at least one supplied field from `{shop_name,description,logo_url,shop_category_id,theme_id}`. Profile field validation matches `/seller/profile`. Explicit null is allowed for description, logo and category, but not name/theme. Theme must be `gallery`, `linen` or `clay`; invalid values return `422 INVALID_SHOP_THEME`. New category assignments require an ACTIVE category (`422 CATEGORY_UNAVAILABLE`); the current disabled category can be retained. Unknown fields and client-supplied seller/account/status fields are rejected with `422 VALIDATION_ERROR`.

Updates lock and recheck the caller's seller, validate before changing fields, and commit atomically. Saving does not change seller approval, audit history or product categories. The onboarding `/seller/profile` endpoint remains editable only in DRAFT. Apply migration `0004_shop_settings` before using the updated API. The approved-seller Shop settings UI is implemented. Public buyer pages remain future work.

### Seller products

Product management endpoints require an authenticated ACTIVE Seller. Ownership is always taken from the current account; foreign and unknown products/images return 404. Mutations use the existing CSRF and Origin checks. No seller/actor IDs are accepted in product payloads.

- `GET /seller/products?page=0&page_size=20&status=DRAFT` returns `{items,total,page,page_size}`. Status is optional; page is zero-based and size is 1–100. Results sort by creation time descending, then UUID.
- `POST /seller/products` creates a product (201). `PUT /seller/products/{id}` replaces the editable fields (200). Both accept `{name,description,category_id,price,stock,status}`. Name is trimmed, nonblank, up to 255 characters; description is optional up to 10,000. Price is nonnegative, numeric(12,2), at most two decimal places, and serialized as a decimal string. Stock is an integer from 0 to 2147483647. Status is DRAFT (default), ACTIVE, INACTIVE or SOLD_OUT. There is no automatic stock/status transition in this phase. No currency is inferred; selecting a currency remains a product decision before checkout.
- `GET /seller/products/{id}` and writes return `{id,name,description,category_id,price,stock,status,created_at,updated_at,images}`. Each image has `{id,url,sort_order}`. Images are sorted in upload order; the first is the cover.
- `DELETE /seller/products/{id}` returns 204 and removes its images. A product referenced by a cart, order or review returns `409 PRODUCT_IN_USE`; references are preserved. The seller can choose INACTIVE instead.
- `GET /categories?page=0&page_size=20` publicly returns `{items,total,page,page_size}`, with active categories sorted by name then UUID. Each item has `{id,parent_id,name,slug}`. New product assignments require an active category (`422 CATEGORY_UNAVAILABLE` otherwise). An existing product can retain its current disabled category while other fields are edited.
- `POST /seller/products/{id}/images` takes the image file bytes as the request body, with `Content-Type: image/jpeg`, `image/png` or `image/webp` (not JSON or multipart). Returns the new image with 201. The streamed body is bounded to 5 MiB (413 on excess); decoded dimensions are bounded to 16 million pixels. Empty, mismatched, malformed, animated and unsupported files return `422 INVALID_PRODUCT_IMAGE`. Files are decoded and re-encoded without original metadata, stored with generated UUID filenames, and served publicly under `/media/products/{filename}` only while their database record exists. No source filename or remote URL is accepted. Local uploads are development-only; production returns `503 LOCAL_UPLOADS_DEVELOPMENT_ONLY` until durable storage is integrated.
- `DELETE /seller/products/{id}/images/{imageId}` returns 204. Database writes commit before local files are removed; failed image inserts clean up their new file. If post-commit file cleanup fails, the orphan is logged and no longer served. A process crash between disk and database writes may leave an orphan; local storage is not a distributed transaction.

Product publication controls stored status and public eligibility as described above; public buyer product listing/detail is implemented in storefront step 2. Products and media use existing schema tables; no migration is added. Development-only sample categories and a local Admin can be provisioned explicitly with `python -m app.seed_dev`; existing users are never promoted and existing passwords are not reset.

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

### Seller review (Phase 4.2)

Review endpoints require a valid authenticated account and an Admin profile with `status = ACTIVE`. Inactive Admin profiles do not receive the ADMIN role. State-changing requests also require the CSRF cookie/header and trusted Origin checks.

`GET /admin/sellers?status=PENDING&page=0&page_size=20` returns a paginated queue. `status` accepts `DRAFT`, `PENDING`, `ACTIVE`, `REJECTED`, or `SUSPENDED` and defaults to `PENDING`; page is zero-based, page size defaults to 20 and is bounded from 1 to 100. Results are deterministically ordered by submission time (newest first; legacy records without a submission event use creation time) and seller UUID. The response is `{ "items": [{ "seller_id", "shop_name", "seller_status", "created_at", "updated_at", "submitted_at" }], "total", "page", "page_size" }`. Submitted time is derived from the existing audit event; no column was added. Only explicit seller fields are returned.

`GET /admin/sellers/{sellerId}` returns seller ID, shop name, description, logo URL, status, profile timestamps, and ordered lifecycle `history`. Each history item contains previous/new status, action, timestamp, actor type, optional Admin display name, and reason. It does not return account email, password hash, tokens, or actor account IDs. Unknown sellers return `404 SELLER_NOT_FOUND`.

`POST /admin/sellers/{sellerId}/approve` accepts no body and changes only `PENDING` to `ACTIVE`. `POST /admin/sellers/{sellerId}/reject` accepts `{ "reason": "..." }`; the trimmed reason must contain 1–2000 characters. It changes only `PENDING` to `REJECTED`. Both return `{ "seller_id", "seller_status", "decided_at" }` and append `APPLICATION_APPROVED` or `APPLICATION_REJECTED` to `seller_status_history` in the same transaction. Actor identity comes from the authenticated Admin context. A seller cannot decide their own application. A missing seller returns 404, an inactive/insufficient role returns 403, and stale/invalid transitions return `409 SELLER_DECISION_CONFLICT`; missing/blank/oversized reasons return 422. Conditional status updates serialize competing decisions: exactly one can succeed and the loser receives 409 without an audit event.

Admin approval/rejection is implemented. Seller resubmission and suspension remain future workflows.

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
