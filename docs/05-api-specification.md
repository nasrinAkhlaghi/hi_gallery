# HI Gallery — API Specification

Base URL: `/api/v1`
Format: JSON, UUID identifiers, ISO-8601 timestamps.

## Authentication
- POST `/auth/register`
- POST `/auth/register/seller`
- POST `/auth/login`
- POST `/auth/logout`

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
