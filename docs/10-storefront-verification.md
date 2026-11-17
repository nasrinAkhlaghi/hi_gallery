# HI Gallery — Storefront Verification

## Status

Steps 1–5 are complete for the scoped storefront increment. Automated checks and the live registration-to-publication flow passed. Responsive verification covered all three themes in English and Persian at 320, 390, 768 and 1280 px, plus product detail and mobile Seller Studio. This verifies storefront browsing/customization; purchasing and production media storage remain separate work.

All manual data was synthetic. The full browser flow used a separate throwaway PostgreSQL database. Responsive and short-expiry checks used an isolated in-memory database with the real API routes, separate API/frontend ports and test-only media. The configured development database and existing accounts/products were not modified.

## Automated verification

- Backend: 145 tests passed, including all six previously skipped PostgreSQL migration/concurrency checks and the new complete storefront flow test. No PostgreSQL checks were skipped in this run.
- `tests/test_storefront_flow.py` exercises real registration, login, draft onboarding, application submission, Admin approval, shop settings, product creation, image upload and serving, publication, signed-out search/category/shop/detail discovery, all three theme IDs, unpublication, sold-out state and account suspension. It confirms that shop category edits do not change product categories or seller approval history.
- Frontend: 88 tests passed and the production build succeeded. Regression coverage includes signed-out navigation, filters/pagination, stale response handling, image selection/fallback, shop preview isolation, saved theme scope and Persian RTL.
- Added idle-session regressions: refresh and logout obtain a CSRF token bound to current cookies instead of reusing a token tied to an expired access cookie. Existing concurrent-refresh deduplication remains covered.

Run frontend checks from `frontend/` with `npm test` and `npm run build`. Run backend checks from `backend/` with `python -m pytest -q`. Enable PostgreSQL checks only with `TEST_DATABASE_URL` pointing to a separate disposable database and `TEST_DATABASE_ISOLATED=1`; never use the development/production database for these checks.

## Browser observations

| Check | Result |
| --- | --- |
| Register maker, sign in, save profile and submit application | Passed against live API/PostgreSQL |
| Admin review and approval; approved Seller Studio navigation | Passed |
| Select primary category and Clay theme | Passed |
| Open public shop before saving theme | Still Gallery; unsaved preview remained local |
| Save settings and reload public shop | Saved Clay theme visible |
| Create draft product | Public shop remained empty |
| Upload synthetic PNG through browser file input | Passed on retry after idle-session interruption |
| Publish product and sign out | Product image, name, decimal price and seller link visible publicly |
| Desktop public shop, English and Persian RTL | Inspected; English desktop screenshot captured |
| Gallery/Linen/Clay persistence and visibility | API/component checks and responsive browser inspection passed |
| All three themes × EN/FA × 320/390/768/1280 px | 24 measured browser checks passed without horizontal overflow after the narrow-screen fix |
| Product detail × EN/FA × the same four widths | 8 measured checks passed without horizontal overflow |
| Mobile Seller Studio in EN/FA | Menu, form layout, native keyboard theme selection and Discard passed |
| Keyboard skip link and search submission | Skip link focused main content; Enter submitted search |
| Search/category composition, pagination and browser Back | Passed with 25 synthetic products; page 2 showed 5 cards |
| No-result search, sold-out detail, missing product and broken image | Correct states/fallback observed in the browser |
| Access-cookie expiry during Save | Live request trace: PATCH 401 → CSRF 200 → refresh 200 → CSRF 200 → retried PATCH 200 |
| Access-cookie expiry before logout | Current CSRF fetched; logout returned 204 and sign-in UI appeared |

The first delayed upload exposed an expired-cookie/CSRF refresh bug: the upload received 401, then refresh received 403 because its cached CSRF token still referenced the previous access cookie. The frontend now fetches current CSRF state before refresh and logout, and refresh obtains the new access-bound token before retrying the original request. The subsequent browser upload and publication succeeded. The expiry fix also passed a live browser test with five-second access cookies in the isolated QA server, plus dedicated automated regressions. The production token lifetime remains unchanged.

The product-form publication hint was also updated to reflect that public browsing is available.

## Narrow-screen fix and evidence

The original global `body` minimum width was 320 px. At a 320 px viewport with a visible scrollbar, only 305 px were available, producing a 15 px overflow (on the left in RTL). Removing that minimum allowed the responsive layouts to use the available width. All 24 theme/language/size checks, the 8 product-detail checks and mobile Seller Studio then measured content width no greater than client width.

Verify the active tab's measured viewport when testing: a background tab can retain another size. Screenshots were captured from settled viewport views; local evidence includes Persian mobile Gallery/Linen/Clay shops and product detail, plus the initial English desktop shop. Temporary viewport overrides were reset after verification.

Remaining product work is outside this increment: cart, checkout, payment, reviews and durable production media storage. Repeat this responsive and full-flow regression matrix after changes to navigation, product cards, themes or authentication.

Cart, checkout, payment and reviews remain separate future increments. This verification does not represent purchase-flow or production-storage readiness.
