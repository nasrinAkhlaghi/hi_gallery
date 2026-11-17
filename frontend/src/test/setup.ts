import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

const testUser = {
  id: "00000000-0000-4000-8000-000000000001",
  email: "buyer@example.com",
  roles: ["BUYER", "SELLER", "ADMIN"],
  seller_status: "ACTIVE",
};

function installDefaultFetch() {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
  const path = String(input);
  if (path.endsWith("/auth/csrf")) return new Response(JSON.stringify({ csrf_token: "test-csrf" }), { status: 200 });
  if (path.endsWith("/auth/me")) return new Response(JSON.stringify(testUser), { status: 200 });
  if (path.endsWith("/auth/refresh")) return new Response(JSON.stringify(testUser), { status: 200 });
  if (path.endsWith("/auth/logout")) return new Response(null, { status: 204 });
  if (path.endsWith("/seller/shop")) return new Response(JSON.stringify({ id: "shop-1", shop_name: "Test Studio", description: null, logo_url: null, shop_category_id: null, theme_id: "gallery", updated_at: "2026-11-17T00:00:00Z" }), { status: 200 });
  if (path.includes("/seller/products?") || path.includes("/categories?")) return new Response(JSON.stringify({ items: [], total: 0, page: 0, page_size: 20 }), { status: 200 });
  return new Response(JSON.stringify(testUser), { status: 200 });
  }));
}

installDefaultFetch();
afterEach(installDefaultFetch);
