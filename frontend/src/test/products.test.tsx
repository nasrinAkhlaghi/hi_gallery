import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import i18n from "../i18n";
import { clearCsrfToken } from "../auth/api";
import type { Product } from "../seller/productsApi";

const category = { id: "category-1", name: "Ceramics", slug: "ceramics", parent_id: null };
const seller = { id: "seller-1", email: "maker@example.com", roles: ["SELLER"], seller_status: "ACTIVE" };
const product: Product = { id: "product-1", name: "Clay bowl", description: "Handmade", category_id: category.id,
  price: "12.50", stock: 3, status: "DRAFT", images: [], created_at: "2026-11-16T00:00:00Z", updated_at: "2026-11-16T00:00:00Z" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

function installFetch(handler: (path: string, init?: RequestInit) => Response) {
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    if (path.endsWith("/auth/me")) return json(seller);
    if (path.endsWith("/auth/csrf")) return json({ csrf_token: "test-csrf" });
    if (path.includes("/categories?")) return json({ items: [category], total: 1, page: 0, page_size: 100 });
    return handler(path, init);
  }));
}

function renderAt(path: string) { window.history.replaceState(null, "", path); render(<App />); }

beforeEach(async () => { cleanup(); clearCsrfToken(); await i18n.changeLanguage("en"); });
afterEach(cleanup);

describe("seller product management", () => {
  it("filters and paginates the seller list", async () => {
    const requests: string[] = [];
    installFetch((path) => {
      requests.push(path);
      const query = new URL(path, "http://localhost").searchParams;
      return json({ items: [{ ...product, name: query.get("page") === "1" ? "Second page" : "Clay bowl" }], total: 21, page: Number(query.get("page")), page_size: 20 });
    });
    renderAt("/seller/products");
    expect(await screen.findByRole("heading", { name: "Clay bowl" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByRole("heading", { name: "Second page" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Filter by status"), { target: { value: "ACTIVE" } });
    await waitFor(() => expect(requests[requests.length - 1]).toContain("page=0&page_size=20&status=ACTIVE"));
  });

  it("creates a draft, sends decimal price as a string and uploads an image with CSRF", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    installFetch((path, init) => {
      calls.push({ path, init });
      if (path.endsWith("/images")) return json({ id: "image-1", url: "/media/products/test.png", sort_order: 0 }, 201);
      if (init?.method === "POST") return json({ ...product, ...JSON.parse(String(init.body)) }, 201);
      return json(product);
    });
    renderAt("/seller/products/new");
    const name = await screen.findByLabelText("Product name");
    expect(screen.queryByLabelText("Upload image")).not.toBeInTheDocument();
    fireEvent.change(name, { target: { value: "Clay bowl" } });
    fireEvent.change(screen.getByLabelText("Category"), { target: { value: category.id } });
    fireEvent.change(screen.getByLabelText("Price"), { target: { value: "12.50" } });
    fireEvent.change(screen.getByLabelText("Stock"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    const upload = await screen.findByLabelText("Upload image");
    expect(window.location.pathname).toBe("/seller/products/product-1");
    const createCall = calls.find((call) => call.path.endsWith("/seller/products") && call.init?.method === "POST");
    expect(JSON.parse(String(createCall?.init?.body))).toMatchObject({ price: "12.50", stock: 3, status: "DRAFT" });
    const file = new File(["pixels"], "bowl.png", { type: "image/png" });
    fireEvent.change(upload, { target: { files: [file] } });
    expect(await screen.findByRole("img", { name: "Clay bowl, image 1" })).toBeInTheDocument();
    const uploadCall = calls.find((call) => call.path.endsWith("/images"));
    expect(uploadCall?.init?.body).toBe(file);
    expect(new Headers(uploadCall?.init?.headers).get("X-CSRF-Token")).toBe("test-csrf");
    expect(new Headers(uploadCall?.init?.headers).get("Content-Type")).toBe("image/png");
  });

  it("publishes edits and requires confirmation before deleting a product", async () => {
    const methods: string[] = [];
    installFetch((path, init) => {
      methods.push(init?.method ?? "GET");
      if (init?.method === "DELETE") return new Response(null, { status: 204 });
      if (init?.method === "PUT") return json({ ...product, ...JSON.parse(String(init.body)) });
      if (path.includes("/seller/products?")) return json({ items: [], total: 0, page: 0, page_size: 20 });
      return json(product);
    });
    renderAt("/seller/products/product-1");
    fireEvent.change(await screen.findByLabelText("Product status"), { target: { value: "ACTIVE" } });
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText("Product saved.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete product" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(methods).not.toContain("DELETE");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete product" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm deletion" }));
    expect(await screen.findByText("No products match this view.")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/seller/products");
  });

  it("removes an image after confirmation and preserves unsaved form edits", async () => {
    installFetch((_path, init) => init?.method === "DELETE" ? new Response(null, { status: 204 }) : json({ ...product, images: [{ id: "image-1", url: "/media/products/test.png", sort_order: 0 }] }));
    renderAt("/seller/products/product-1");
    fireEvent.change(await screen.findByLabelText("Product name"), { target: { value: "Unsaved bowl" } });
    fireEvent.click(screen.getByRole("button", { name: "Remove image 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm deletion" }));
    expect(await screen.findByText("Image removed.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Product name")).toHaveValue("Unsaved bowl");
  });

  it("rejects unsupported image types and reports server validation and delete conflicts", async () => {
    installFetch((_path, init) => {
      if (init?.method === "PUT") return json({ code: "CATEGORY_UNAVAILABLE" }, 422);
      if (init?.method === "DELETE") return json({ code: "PRODUCT_IN_USE" }, 409);
      return json(product);
    });
    renderAt("/seller/products/product-1");
    fireEvent.change(await screen.findByLabelText("Upload image"), { target: { files: [new File(["svg"], "bad.svg", { type: "image/svg+xml" })] } });
    expect(screen.getByRole("alert")).toHaveTextContent("Choose a valid, non-animated");
    fireEvent.click(screen.getByRole("button", { name: "Save product" }));
    expect(await screen.findByText("This category is unavailable. Choose an active category.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete product" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm deletion" }));
    expect(await screen.findByText(/referenced by a cart/)).toBeInTheDocument();
  });

  it("shows load errors and allows retry", async () => {
    let fail = true;
    installFetch(() => fail ? json({ code: "ERROR" }, 500) : json({ items: [], total: 0, page: 0, page_size: 20 }));
    renderAt("/seller/products");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No products match this view.")).toBeInTheDocument();
  });

  it("renders the product form in Persian RTL", async () => {
    await i18n.changeLanguage("fa");
    installFetch(() => json(product));
    renderAt("/seller/products/product-1");
    expect(await screen.findByLabelText("نام محصول")).toHaveValue("Clay bowl");
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByRole("button", { name: "ذخیره محصول" })).toBeInTheDocument();
  });
});
