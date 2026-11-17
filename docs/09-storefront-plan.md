# HI Gallery — Storefront and Shop Customization Plan

## Status and scope

Steps 1–3 are implemented in code: additive migration `0004_shop_settings`, seller fields, authenticated shop settings APIs, public shop/product discovery and detail APIs, and the approved-seller Shop settings UI. Apply the migration to a reviewed target database before running the updated API. Buyer pages and complete seller-to-buyer visual verification (steps 4–5) remain planned. The View Shop link currently reaches a public route scaffold; step 4 replaces it with the real shop page. Seller onboarding, Admin approval and approved-seller product management already exist. This document specifies the next connection between Seller Studio and the buyer experience: shop category, shop theme, public shop page, and public product discovery/detail.

The MVP choices below keep the first implementation small: one optional primary shop category, three built-in themes, UUID-based public shop URLs, and explicit saving of shop settings. Additional categories, custom themes and shop slugs can be added later.

## Seller experience

An ACTIVE seller opens `/seller/shop`, chooses a primary category and theme, edits the shop name, description or logo URL, previews the result, and saves. Provide a link to the public shop page after saving. Unsaved previews must not change what buyers see.

Shop settings reuse the current name, description and logo URL validation. Category is optional and can be cleared; new assignments must reference an ACTIVE category. An existing disabled category may be retained while other settings change. The primary shop category describes the shop; each product still has its own required category, independently selected in Products. Changing the shop category never rewrites or restricts product categories.

Offer these theme IDs: `gallery` (existing warm gallery styling, default), `linen` (light neutral styling), and `clay` (earthy styling). Themes are built-in presentation presets with accessible colors and typography. They do not accept seller HTML, CSS, JavaScript or arbitrary style values. All themes show the same shop and product information and support Persian/RTL and English/LTR.

Product creation stays at `/seller/products/new`: name, description, category, price, stock, status, then images. Link to Products and Add Product from Shop. Only saved products eligible for public visibility appear on the public shop page.

This increment allows ACTIVE sellers to edit shop presentation without changing approval status or submitting a new application. DRAFT sellers keep their current onboarding flow; PENDING, REJECTED and SUSPENDED sellers cannot use these shop-setting mutations. Editing/resubmitting rejected applications remains separate future work.

## Buyer experience and visibility

`/shops/:sellerId` is public, including for signed-out visitors. Show shop name, description, logo or fallback, active primary category if available, and a paginated product grid using the saved theme. Product cards link to `/products/:id`; the seller name on product detail links back to the shop. Provide an empty state for an approved shop without published products.

A public shop requires both an ACTIVE seller and an ACTIVE owning account. Unknown or unavailable shops return 404. Public product listing and detail use the same seller/account eligibility and expose only product statuses ACTIVE and SOLD_OUT. DRAFT and INACTIVE products return 404 on public detail and never appear in public lists. A disabled product category does not unpublish an otherwise eligible product, but it is omitted from active category navigation.

Show SOLD_OUT products and ACTIVE products with zero stock as unavailable for purchase. Do not automatically rewrite product statuses or stock. Cart, checkout and payment remain separate increments; do not present a working purchase action until that flow exists. Display prices without inventing a currency; currency must be decided before checkout implementation.

`/browse` lists eligible products with optional name search and exact product-category filtering. `/categories` uses the active category list and links to Browse with the selected category. Shop product lists can also filter by exact product category. A shop's primary category is informational in this increment; it is not a product filter or a shop-directory feature.

Public responses exclude account/email/actor IDs, application history, rejection reasons and operational seller/order information. Existing local media URLs remain publicly accessible according to their current image-record rules; publication visibility in this increment governs shop/product JSON and pages, not confidential image storage.

## Persistence (step 1 implemented)

Add `seller.shop_category_id`, a nullable UUID foreign key to `category.id`, and `seller.theme_id`, a non-null string defaulting to `gallery` with a constraint allowing `gallery`, `linen`, `clay`. Add an index on `shop_category_id`. Existing sellers receive the default theme and no shop category, preserving their approval state and products.

Migration `0004_shop_settings` adds these fields and constraints; models and `docs/04-database-schema.sql` reflect it. The frozen `backend/alembic/schema.sql` and previous migrations remain unchanged. Downgrade removes the new settings fields and therefore discards saved theme/category choices, while preserving sellers and products.

## Planned API contracts

All paths below are relative to `/api/v1`. Shop settings endpoints are implemented in step 1; public shop/product endpoints are implemented in step 2. Existing `/seller/profile` and onboarding contracts remain unchanged.

### Shop settings (implemented)

- `GET /seller/shop`: authenticated ACTIVE seller; returns `{id,shop_name,description,logo_url,shop_category_id,theme_id,updated_at}` for the caller.
- `PATCH /seller/shop`: same authorization, CSRF and Origin checks as existing seller mutations. Accept only supplied fields from `{shop_name,description,logo_url,shop_category_id,theme_id}`. At least one field is required. Name and theme cannot be null; category, description and logo may be cleared with null. Unknown fields, seller IDs and status fields are rejected. Validate the whole request before an atomic save; return the updated settings shape.
- Invalid theme or unavailable category returns 422 (`INVALID_SHOP_THEME` or `CATEGORY_UNAVAILABLE`). Ownership comes from authentication. No seller ID is accepted in either settings endpoint.

### Public shop and products (implemented)

- `GET /shops/{sellerId}` returns `{id,shop_name,description,logo_url,category,theme_id}`; `category` is `{id,parent_id,name,slug}` for an active primary category, otherwise null.
- `GET /shops/{sellerId}/products?page=0&page_size=20&category_id=...` returns `{items,total,page,page_size}` and 404 when the shop is unavailable. An available empty shop returns 200 with no items.
- `GET /products?page=0&page_size=20&q=...&category_id=...` returns the same page shape. `q` is optional, trimmed, at most 200 characters; empty means no search. Match a case-insensitive literal substring of the product name. Search wildcards supplied by the visitor are treated literally.
- `GET /products/{productId}` returns eligible public product detail or 404.
- `GET /categories/{categoryId}/products` uses the same pagination and public product projection, with an exact category filter. An unknown or inactive category returns 404.

Public product projection: `{id,name,description,category,price,stock,status,images,seller}`. `category` contains `{id,parent_id,name,slug}`; `seller` contains only `{id,shop_name}`; images contain `{id,url,sort_order}` in existing cover-first order. Price remains a decimal string. Do not fabricate ratings or review counts before reviews are implemented.

All product lists use zero-based pages, default size 20, allowed sizes 1–100, and sort by creation time descending then UUID. Category filters match the exact category, without implicit descendants. A well-formed filter with no eligible matches returns an empty page. Invalid UUIDs, pagination or query values return 422. Every public query applies visibility before pagination and total counting. Detail, Browse, category results and shop results must share these rules.

## Implementation order

1. **Implemented in code:** migration, model fields and settings API with authorization/validation coverage. The PostgreSQL legacy-data upgrade/downgrade check is opt-in and requires a separate disposable test database.
2. **Implemented in code:** shared public visibility queries, shop/product endpoints and contract tests. Direct detail URLs, lists and totals enforce the same visibility rules.
3. **Implemented in code:** `/seller/shop` settings, scoped theme previews, explicit save/discard feedback, category edge cases, product links and a public shop link. English/Persian labels and approval guards are covered by component tests. The public shop destination is a scaffold until step 4; browser visual verification remains pending.
4. Build `/shops/:sellerId`, `/browse`, `/categories` and `/products/:id`; connect seller links and category navigation to real data.
5. Verify the complete seller-to-buyer flow in English and Persian on desktop and mobile; update the manual testing guide and implementation status.

## Acceptance checks

- An approved seller saves a category and theme, creates a categorized product with images, marks it ACTIVE, and a signed-out buyer sees it in that seller's public shop, Browse and product detail.
- Theme and category survive reload; an unsaved preview never affects another visitor. Product category remains independent from shop category.
- Saving shop details does not alter seller approval state. Another seller cannot change these settings; non-ACTIVE sellers cannot mutate them.
- Legacy sellers render with `gallery` and no primary category. Invalid categories/themes fail without partial writes.
- A DRAFT/INACTIVE product cannot be fetched through public lists or a guessed detail URL. An unavailable seller or account hides its shop and products consistently.
- An approved shop with no eligible products displays a useful empty state. SOLD_OUT and zero-stock products show availability correctly.
- Pagination counts include only visible products. Search and category filters compose without leaking another shop's products into shop results.
- Loading, empty, validation, save-success, error/retry and 404 states work with keyboard navigation and readable mobile RTL layouts.
- Existing onboarding, Admin approval and seller product management continue to pass their relevant checks. Cart/checkout are not acceptance requirements for this increment.
