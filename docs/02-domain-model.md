# HI Gallery — Domain Model

## Entities
- Account: authentication credentials and lifecycle.
- Buyer: one-to-one with Account.
- Seller: one-to-one with Account; owns products.
- SellerStatusHistory: append-only seller lifecycle event with actor type/identity and transition data.
- Admin: one-to-one with Account.
- Category: hierarchical product classification.
- Product: belongs to exactly one Seller and Category.
- ProductImage: belongs to one Product.
- Cart: active cart of one Buyer.
- CartItem: Product + quantity.
- Order: complete Buyer purchase; may contain multiple sellers.
- SellerOrder: seller-specific portion of an Order.
- OrderItem: purchased product snapshot within SellerOrder.
- Payment: payment state for an Order.
- Review: Buyer review of purchased Product.

## Relationships
Account 1—0..1 Buyer
Account 1—0..1 Seller
Account 1—0..1 Admin
Seller 1—N Product
Seller 1—N SellerStatusHistory
Category 1—N Product
Category 1—N Category
Product 1—N ProductImage
Buyer 1—1 Cart
Cart 1—N CartItem
CartItem N—1 Product
Buyer 1—N Order
Order 1—N SellerOrder
Seller 1—N SellerOrder
SellerOrder 1—N OrderItem
OrderItem N—1 Product
Order 1—N Payment
Buyer 1—N Review
Product 1—N Review
Order 1—N Review

## Invariants
- Seller may modify only own products/orders.
- New seller profiles begin in `DRAFT`; explicit submission changes `DRAFT` to `PENDING`. Existing PENDING records are preserved by migration.
- Seller lifecycle transitions are recorded in `seller_status_history` in the same transaction. `actor_type` identifies SELLER or ADMIN; actor identity comes from authenticated context (or the seller account during registration), never from request input.
- Phase 4.1 history starts with registration (`NULL` → `DRAFT`) and submission (`DRAFT` → `PENDING`); no historical events are fabricated for existing sellers. Active Admin decisions append `PENDING` → `ACTIVE` or `PENDING` → `REJECTED` events, including the required rejection reason.
- Admin authorization requires an authenticated account with an Admin profile whose status is `ACTIVE`. An inactive Admin profile does not grant the ADMIN role.
- Seller review decisions are conditional on the current `PENDING` status and update the seller and append audit history in one transaction. A seller cannot review their own application.
- OrderItem seller must match SellerOrder seller.
- Prices and stock cannot be negative.
- CartItem/OrderItem quantity must be positive.
- Review rating is 1–5.
- Buyer + product + order uniquely identifies a review.

## Product Group
Not an MVP transactional entity. Future grouping may be performed by Admin or AI. Equal product names do not mean equal products.

## Aggregate Guidance
Use clear module boundaries around Account, Buyer, Seller, Product, Cart, Order/SellerOrder, Review. Avoid uncontrolled cross-module persistence access.
