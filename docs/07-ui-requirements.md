# HI Gallery — UI Requirements

## Design Direction
HI Gallery should feel like a curated handmade gallery rather than a generic mass-market e-commerce site.

Brand idea: `HI = Human Intelligence`.

Visual goals:
- Human-made
- Handmade
- Craftsmanship
- Trust
- Discovery
- Warmth
- Quality

Do not copy Amazon's visual language.

## Stack
React + TypeScript + Vite + Tailwind CSS + shadcn/ui.

## Buyer Navigation
HI Gallery, Search, Categories, Cart, Orders, Profile.

## Buyer Pages
Home, Browse, Categories, Product Details, Cart, Checkout, Orders, Reviews, Profile.

Home should prioritize:
1. Value proposition
2. Search
3. Categories
4. Featured products
5. Recently added/discovery

Product cards show image, name, price, seller, rating/review count when available.

Product detail shows image gallery, name, price, seller, description, rating/reviews, stock, quantity, Add to Cart, category.

## Seller Studio
Distinct visual experience from shopping.

Navigation:
Dashboard, Products, Orders, Shop, Settings.

Seller onboarding uses the shared Seller layout at `/seller/onboarding`. Non-ACTIVE sellers see the onboarding destination instead of approved-only Seller Studio navigation. DRAFT sellers can edit shop name, optional description and optional logo URL, save the profile, and explicitly confirm “Submit for Review”. PENDING sellers can view their profile and application status but cannot edit or submit again. REJECTED sellers see the decision reason and cannot edit or resubmit in Phase 4.2. Show lifecycle states distinctly with loading, success, validation, conflict, and error feedback. ACTIVE sellers retain the existing Seller Studio navigation and may view their profile.

Dashboard cards:
- Active products
- Pending orders
- Orders requiring action
- Completed orders

Product form:
Name, description, category, price, stock, images, save/publish.

Do not expose Product Group as a seller field.

Seller order detail shows only that seller's items plus required shipping information.

## Shop Customization and Public Shop

`/seller/shop` now provides name/description/logo settings, an optional primary shop category, and built-in theme cards (`gallery`, `linen`, `clay`) with a selected state and unsaved preview. Include explicit Save, save/error feedback, View Shop, Products and Add Product links. Only ACTIVE sellers can use these settings. Shop category is independent from the required category in the product form.

Public `/shops/:sellerId` now shows the saved theme, shop identity, active primary category if available and a paginated product grid. Product detail links to the seller's shop. Implement Browse and Categories with real public data. Preserve loading, empty, retry, unavailable and 404 states; show sold-out/zero-stock availability and do not imply checkout works before it is implemented. Theme previews and public pages must support accessible colors, keyboard use, mobile layouts, Persian RTL and English LTR.

Shop settings and its local preview are implemented with English/Persian labels, save/discard controls, preserved edits on failed saves, and non-ACTIVE seller guards. The public shop link opens the real shop. Step 4 buyer pages are implemented, including category links from Home, URL-based Browse filters, product galleries, sold-out/zero-stock availability, and loading/empty/error states. Browser visual verification remains pending; cart/checkout are separate increments. [Storefront plan](09-storefront-plan.md) defines detailed behavior, API contracts, implementation order and acceptance checks.

## Admin Console
Distinct operational interface.

Navigation:
Dashboard, Sellers, Buyers, Products, Orders, Reviews, Reports.

Dashboard metrics:
Seller count, buyer count, product count, order count, pending seller approvals.

Admin tables should support useful search/filter/pagination and confirmation for destructive actions.

Seller review at `/admin/sellers` defaults to a PENDING application queue with status filtering and bounded pagination. `/admin/sellers/:sellerId` shows shop name, description, optional logo, status, and ordered lifecycle history. ACTIVE Admins can explicitly confirm approval or provide a required rejection reason. Show loading, empty, error, and stale-decision conflict states. Keep approval/rejection controls unavailable once the application is no longer PENDING. Provide English and Persian labels and preserve readable RTL layout for the filter, history, forms, and pagination.

## Responsive
Desktop, tablet, mobile. Mobile must be intentionally designed.

## Accessibility
Use semantic HTML, keyboard navigation, accessible labels, readable contrast, non-color-only status indicators, and useful loading/empty/error states.

## AI UX — Future
AI features should be presented as helpful enhancements such as:
- Search by description
- Similar products
- You may also like
- Suggested category

AI output must not be presented as unquestionable truth.

## UX Priority
1. Product discovery
2. Product clarity
3. Trust
4. Checkout simplicity
5. Seller usability
6. Admin efficiency
