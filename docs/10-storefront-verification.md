# HI Gallery — Storefront Verification

## Status

Steps 1–4 are implemented. Step 5 is partially verified: the automated backend suite passed against isolated SQLite fixtures and a disposable PostgreSQL 16 database, and the real browser flow passed through registration, approval, shop customization, image upload, publication and signed-out discovery. Mobile visual verification remains open because the browser connection became suspended during viewport testing. Do not treat this report as full mobile sign-off.

All manual data was synthetic. The browser used a separate database inside a throwaway PostgreSQL container, a separate API/frontend port pair and a test-only media directory. The configured development database and existing accounts/products were not modified.

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
| Gallery/Linen/Clay persistence and visibility | API and component tests passed; complete visual comparison remains open |
| Actual mobile viewport and full responsive flow | Not signed off; browser network suspension prevented completion |

The first delayed upload exposed an expired-cookie/CSRF refresh bug: the upload received 401, then refresh received 403 because its cached CSRF token still referenced the previous access cookie. The frontend now fetches current CSRF state before refresh and logout, and refresh obtains the new access-bound token before retrying the original request. The subsequent browser upload and publication succeeded; the expiry-specific fix has dedicated automated coverage.

The product-form publication hint was also updated to reflect that public browsing is available.

## Remaining checks

1. Complete actual 320/390 px mobile, tablet and desktop inspection for all three themes in both languages. Confirm the measured DOM viewport matches the requested size; a background tab may retain a different viewport from the active tab.
2. Verify keyboard navigation/focus, long text, broken images, unavailable shops/products, empty/filter/no-result states and product-detail gallery layout in the browser.
3. Verify live browser search/category/pagination/back-forward behavior and a refreshed seller session after real idle expiry. The automated contracts pass; complete this manual matrix before marking step 5 finished.

Cart, checkout, payment and reviews remain separate future increments. This verification does not represent purchase-flow or production-storage readiness.
