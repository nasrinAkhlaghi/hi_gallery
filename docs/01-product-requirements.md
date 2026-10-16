# HI Gallery — Product Requirements

## Product
HI Gallery (Human Intelligence Gallery) is an online marketplace focused on handmade and human-created products. It connects independent creators with buyers.

## Roles
### Buyer
Register/login, browse/search products, browse categories, view product details, manage cart, checkout/pay, view orders, review purchased products, report problems.

### Seller
Register, complete a store profile, explicitly submit it for Admin review, then after approval create/manage own products, select categories, upload images, set price/stock, view/manage own seller orders, and view sales information.

### Admin
View platform statistics, manage sellers and approvals, view buyers/products/orders/reviews, moderate content and reports.

## Core Rules
1. A Product belongs to exactly one Seller.
2. Different sellers may independently create similar products.
3. Seller chooses a Category; Seller does not control Product Groups.
4. Product Groups are a future AI/admin concept and are not in the MVP schema.
5. One Buyer Order may contain products from multiple sellers.
6. One SellerOrder is created per seller within an Order.
7. A seller sees only their own SellerOrders and related items.
8. Buyers can review purchased products.
9. Backend authorization is the security boundary.

## MVP
Authentication, seller profile completion and explicit application submission, seller approval, product CRUD, categories, images, browse/search, cart, checkout, orders/SellerOrders, payment abstraction, reviews, admin dashboard/management.

## Out of MVP
Product Groups, automatic merging, AI search/recommendations, AI descriptions/image recognition, wishlist, following/social feed, messaging, coupons/loyalty/subscriptions, multi-language/currency, advanced shipping/analytics, microservices, Kafka, Kubernetes, Elasticsearch.

## Future AI
Semantic search, product similarity, category suggestions, recommendations. PostgreSQL remains the transactional source of truth.

## Success Flow
Seller registration → Admin approval → Product creation → Buyer discovery → Cart → Checkout → Payment → Order → Seller fulfillment → Buyer review.

## Development Principles
Keep MVP simple and incremental. Do not invent business rules. Ask when specifications conflict. Avoid unnecessary infrastructure. Preserve existing functionality.
