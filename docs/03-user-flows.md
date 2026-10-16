# HI Gallery — User Flows

## Authentication
Buyer: Register → Account → Buyer Profile → Login → Buyer Home.
Seller: Register → DRAFT store profile → Edit shop name and optional description/logo URL → Explicitly submit for review → PENDING → (Phase 4.2 Admin decision) ACTIVE or REJECTED → ACTIVE sellers use Seller Studio.
Admin: Login → Admin Console.

## Buyer
Home → Search/Category → Product List → Product Details → Add to Cart → Cart → Checkout → Payment → Order Confirmation.

## Seller Product
Seller Studio → Products → Add Product → Name/Description → Category → Price/Stock → Images → Save/Publish.

In Phase 4.1, a DRAFT seller can access only onboarding/profile routes, save the store profile, and submit it for review. A PENDING seller can view the profile and status but cannot edit or use approved-only seller actions. Existing PENDING sellers remain pending. Rejected-seller editing/resubmission is planned; Admin decisions are not part of Phase 4.1.

## Seller Orders
Seller Studio → Orders → SellerOrder → Buyer shipping information → Process → Ship → Deliver.

## Admin Approval
Admin → Sellers → Pending Seller → Review → Approve/Reject.

## Reviews
Buyer → Orders → Eligible delivered product → Rating/comment → Submit Review.

## Authorization Errors
Unauthenticated protected request → 401.
Authenticated user without permission → 403.
Unknown resource → 404.

## Priority
1 Authentication
2 Seller registration/approval
3 Product creation
4 Buyer browsing
5 Cart
6 Checkout
7 Orders
8 Seller order management
9 Reviews
10 Admin dashboard

## Future AI
Natural-language query → AI/Search → normal product list.
Product → Similarity → similar products.
Seller product draft → AI category suggestion → seller confirms/changes.
