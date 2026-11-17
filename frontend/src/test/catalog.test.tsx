import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import i18n from "../i18n";
import { clearCsrfToken } from "../auth/api";
import type { PublicProduct, PublicShop } from "../buyer/catalogApi";

const category = { id: "category-1", parent_id: null, name: "Ceramics", slug: "ceramics" };
const otherCategory = { ...category, id: "category-2", name: "Textiles", slug: "textiles" };
const product: PublicProduct = { id: "product-1", name: "Clay bowl", description: "Shaped by hand.", category,
  price: "12.50", stock: 3, status: "ACTIVE", images: [{ id: "image-1", url: "/media/products/bowl.png", sort_order: 0 }, { id: "image-2", url: "/media/products/detail.png", sort_order: 1 }], seller: { id: "shop-1", shop_name: "Clay Studio" } };
const shop: PublicShop = { id: "shop-1", shop_name: "Clay Studio", description: "Made slowly", logo_url: null, category: otherCategory, theme_id: "clay" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const page = (items = [product], total = items.length, number = 0) => json({ items, total, page: number, page_size: 20 });

function installFetch(handler?: (url: URL) => Response | Promise<Response>) {
  const calls: URL[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
    const url = new URL(String(input), "http://localhost");
    url.pathname = url.pathname.replace(/^\/api\/v1/, "");
    calls.push(url);
    if (url.pathname === "/auth/csrf") return json({ csrf_token: "test" });
    if (url.pathname.startsWith("/auth/")) return json({ code: "AUTHENTICATION_REQUIRED" }, 401);
    if (url.pathname === "/categories") return json({ items: [category, otherCategory], total: 2, page: 0, page_size: 100 });
    if (handler) return handler(url);
    if (url.pathname === "/shops/shop-1") return json(shop);
    if (url.pathname === "/products/product-1") return json(product);
    return page();
  }));
  return calls;
}
function renderAt(path: string) { window.history.replaceState(null, "", path); return render(<App />); }
beforeEach(async () => { cleanup(); clearCsrfToken(); await i18n.changeLanguage("en"); });
afterEach(cleanup);

describe("public buyer catalog", () => {
  it("browses while signed out and composes URL search/category filters with pagination", async () => {
    const calls = installFetch((url) => page([{ ...product, name: url.searchParams.get("page") === "1" ? "Second bowl" : "Clay bowl" }], 21, Number(url.searchParams.get("page"))));
    renderAt("/browse");
    await screen.findByRole("heading", { name: "Clay bowl" });
    expect(window.location.pathname).toBe("/browse");
    expect(await screen.findByRole("link", { name: "Sign in" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search products"), { target: { value: "  clay %_  " } });
    fireEvent.submit(screen.getByRole("form", { name: "Find products" }));
    await waitFor(() => expect(new URLSearchParams(window.location.search).get("q")).toBe("clay %_"));
    fireEvent.change(screen.getByLabelText("Product category"), { target: { value: category.id } });
    await screen.findByRole("heading", { name: "Clay bowl" });
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await screen.findByRole("heading", { name: "Second bowl" });
    const request = calls.filter((url) => url.pathname === "/products").slice(-1)[0]!;
    expect(Object.fromEntries(request.searchParams)).toEqual({ page: "1", page_size: "20", q: "clay %_", category_id: category.id });
    fireEvent.change(screen.getByLabelText("Product category"), { target: { value: otherCategory.id } });
    await screen.findByRole("heading", { name: "Clay bowl" });
    expect(new URLSearchParams(window.location.search).has("page")).toBe(false);
    fireEvent.click(screen.getByRole("link", { name: "Clear filters" }));
    await waitFor(() => expect(window.location.search).toBe(""));
  });

  it("restores direct-entry filters and rejects stale results from an earlier request", async () => {
    let finish: (response: Response) => void = () => {};
    installFetch((url) => url.searchParams.get("q") === "old" ? new Promise<Response>((resolve) => { finish = resolve; }) : page([{ ...product, name: "Fresh piece" }]));
    renderAt(`/browse?q=old&category_id=${category.id}&page=2`);
    expect(screen.getByLabelText("Search products")).toHaveValue("old");
    expect(await screen.findByText("Loading products…")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search products"), { target: { value: "fresh" } });
    fireEvent.submit(screen.getByRole("form", { name: "Find products" }));
    await screen.findByRole("heading", { name: "Fresh piece" });
    finish(page([{ ...product, name: "Stale piece" }]));
    await waitFor(() => expect(screen.queryByRole("heading", { name: "Stale piece" })).not.toBeInTheDocument());
  });

  it("links categories to exact filters and products to detail and the maker's shop", async () => {
    installFetch();
    renderAt("/categories");
    fireEvent.click(await screen.findByRole("link", { name: /Ceramics/ }));
    expect(window.location.pathname).toBe("/browse");
    expect(new URLSearchParams(window.location.search).get("category_id")).toBe(category.id);
    const title = await screen.findByRole("heading", { name: "Clay bowl" });
    fireEvent.click(title.closest("a")!);
    await screen.findByRole("heading", { level: 1, name: "Clay bowl" });
    expect(window.location.pathname).toBe("/products/product-1");
    fireEvent.click(screen.getByRole("link", { name: "Clay Studio" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Clay Studio" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/shops/shop-1");
  });

  it("uses the saved shop theme and product category filter independently from its primary category", async () => {
    const calls = installFetch((url) => url.pathname === "/shops/shop-1" ? json(shop) : page());
    renderAt("/shops/shop-1");
    await screen.findByRole("heading", { level: 1, name: "Clay Studio" });
    expect(document.querySelector('[data-shop-theme="clay"]')).toHaveStyle({ backgroundColor: "#f3e5da" });
    expect(screen.getByLabelText("Product category")).toHaveValue("");
    expect(screen.getByText("Textiles", { selector: "p" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Product category"), { target: { value: category.id } });
    await waitFor(() => expect(calls.some((url) => url.pathname === "/shops/shop-1/products" && url.searchParams.get("category_id") === category.id)).toBe(true));
    expect(calls.filter((url) => url.pathname === "/products")).toHaveLength(0);
    expect(screen.getByRole("navigation", { name: "Main navigation" }).closest("header")).not.toHaveStyle({ backgroundColor: "#f3e5da" });
  });

  it("switches gallery images and offers no working purchase action", async () => {
    installFetch(); renderAt("/products/product-1");
    await screen.findByRole("heading", { level: 1, name: "Clay bowl" });
    const mainImage = screen.getByRole("img", { name: "Clay bowl" });
    expect(mainImage).toHaveAttribute("src", expect.stringContaining("/media/products/bowl.png"));
    fireEvent.click(screen.getByRole("button", { name: "View image 2 of Clay bowl" }));
    expect(screen.getByRole("img", { name: "Clay bowl" })).toHaveAttribute("src", expect.stringContaining("/media/products/detail.png"));
    expect(screen.getByRole("button", { name: "View image 2 of Clay bowl" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("12.50")).toBeInTheDocument();
    expect(screen.getByText("3 available")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Add to Cart|Buy/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Online purchasing will be available soon/)).toBeInTheDocument();
    fireEvent.error(screen.getByRole("img", { name: "Clay bowl" }));
    expect(screen.getByRole("img", { name: "No image for Clay bowl" })).toBeInTheDocument();
  });

  it.each(["SOLD_OUT", "ACTIVE"] as const)("shows %s zero-stock products as sold out on cards and detail", async (status) => {
    const unavailable = { ...product, stock: 0, status };
    installFetch((url) => url.pathname === "/products/product-1" ? json(unavailable) : page([unavailable]));
    renderAt("/browse"); await screen.findByText("Sold out");
    fireEvent.click(screen.getByRole("heading", { name: "Clay bowl" }).closest("a")!);
    expect(await screen.findByText("Sold out")).toBeInTheDocument();
    expect(screen.queryByText(/available$/)).not.toBeInTheDocument();
  });

  it.each(["/shops/missing", "/products/missing"])("shows a useful unavailable state on %s", async (path) => {
    installFetch(() => json({ code: "NOT_FOUND" }, 404)); renderAt(path);
    expect(await screen.findByRole("alert")).toHaveTextContent(/unavailable or could not be found/);
    expect(screen.getByRole("link", { name: "Back to Browse" })).toHaveAttribute("href", "/browse");
  });

  it("shows empty shop/results and permits a failed request retry", async () => {
    let fail = true;
    installFetch((url) => url.pathname === "/shops/shop-1" ? json(shop) : fail ? json({ code: "ERROR" }, 500) : page([]));
    renderAt("/shops/shop-1");
    expect(await screen.findByRole("alert")).toHaveTextContent("We could not load this view");
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("This maker has no published pieces yet. Come back soon.")).toBeInTheDocument();
  });

  it("returns to the first page from an empty page and preserves direct category filters", async () => {
    installFetch((url) => page(url.searchParams.get("page") === "5" ? [] : [product], 1, Number(url.searchParams.get("page"))));
    renderAt(`/browse?category_id=disabled-category&page=5`);
    expect(await screen.findByRole("option", { name: "Selected category" })).toHaveValue("disabled-category");
    fireEvent.click(await screen.findByRole("button", { name: "First page" }));
    await screen.findByRole("heading", { name: "Clay bowl" });
    expect(new URLSearchParams(window.location.search).get("category_id")).toBe("disabled-category");
  });

  it("uses Persian RTL on shop, gallery and search controls", async () => {
    await i18n.changeLanguage("fa"); installFetch(); renderAt("/shops/shop-1");
    await screen.findByRole("heading", { level: 1, name: "Clay Studio" });
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getByLabelText("دسته‌بندی محصول")).toBeInTheDocument();
    const card = await screen.findByRole("heading", { name: "Clay bowl" });
    fireEvent.click(card.closest("a")!);
    expect(await screen.findByRole("button", { name: "نمایش تصویر 2 از Clay bowl" })).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("navigation", { name: "مسیر محصول" })).getByRole("link", { name: "مرور محصولات" }));
    expect(await screen.findByLabelText("جست‌وجوی محصولات")).toBeInTheDocument();
  });
});
