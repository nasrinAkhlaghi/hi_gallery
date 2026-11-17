import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import i18n from "../i18n";
import { clearCsrfToken } from "../auth/api";
import type { ShopSettings } from "../seller/shopApi";

const category = { id: "category-1", parent_id: null, name: "Ceramics", slug: "ceramics" };
const original: ShopSettings = { id: "shop-1", shop_name: "Clay Studio", description: "Made slowly", logo_url: null,
  shop_category_id: null, theme_id: "gallery", updated_at: "2026-11-17T00:00:00Z" };
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
type Call = { path: string; init?: RequestInit };

function installFetch(handler: (path: string, init?: RequestInit) => Response | Promise<Response>, status = "ACTIVE", categories = [category]) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const path = String(input);
    calls.push({ path, init });
    if (path.endsWith("/auth/me")) return json({ id: "owner-1", email: "owner@example.com", roles: ["SELLER"], seller_status: status });
    if (path.endsWith("/auth/csrf")) return json({ csrf_token: "shop-csrf" });
    if (path.includes("/categories?")) return json({ items: categories, total: categories.length, page: 0, page_size: 100 });
    if (path.endsWith("/seller/profile")) return json({ ...original, status });
    if (path.endsWith("/seller/application")) return json({ status, can_edit: status === "DRAFT", can_submit: status === "DRAFT" });
    if (path.includes("/shops/shop-1/products?")) return json({ items: [], total: 0, page: 0, page_size: 20 });
    if (path.endsWith("/shops/shop-1")) return json({ ...original, category: null });
    return handler(path, init);
  }));
  return calls;
}

function renderShop() { window.history.replaceState(null, "", "/seller/shop"); return render(<App />); }
const patches = (calls: Call[]) => calls.filter((call) => call.init?.method === "PATCH");

beforeEach(async () => { cleanup(); clearCsrfToken(); await i18n.changeLanguage("en"); });
afterEach(cleanup);

describe("seller shop settings", () => {
  it("loads saved settings and previews theme/details locally, then discards without writing", async () => {
    const calls = installFetch(() => json(original));
    renderShop();
    const name = await screen.findByLabelText("Shop name");
    const preview = screen.getByRole("region", { name: "Shop preview" });
    expect(name).toHaveValue("Clay Studio");
    expect(screen.getByRole("radio", { name: "Gallery" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Save shop" })).toBeDisabled();
    expect(preview).toHaveStyle({ backgroundColor: "#faf6ef" });
    fireEvent.click(screen.getByRole("radio", { name: "Clay" }));
    fireEvent.change(name, { target: { value: "New Studio" } });
    expect(preview).toHaveStyle({ backgroundColor: "#f3e5da" });
    expect(within(preview).getByRole("heading", { name: "New Studio" })).toBeInTheDocument();
    expect(screen.getByText("Unsaved preview")).toBeInTheDocument();
    expect(patches(calls)).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    expect(name).toHaveValue("Clay Studio");
    expect(screen.getByRole("radio", { name: "Gallery" })).toBeChecked();
    expect(preview).toHaveStyle({ backgroundColor: "#faf6ef" });
    expect(patches(calls)).toHaveLength(0);
  });

  it("saves normalized settings with CSRF and restores them on reload", async () => {
    let persisted = { ...original };
    const calls = installFetch((_path, init) => {
      if (init?.method === "PATCH") persisted = { ...persisted, ...JSON.parse(String(init.body)) };
      return json(persisted);
    });
    renderShop();
    fireEvent.change(await screen.findByLabelText("Shop name"), { target: { value: "  Woven Studio  " } });
    fireEvent.change(screen.getByLabelText("Shop description (optional)"), { target: { value: "  Woven by hand  " } });
    fireEvent.change(screen.getByLabelText("Logo URL (optional)"), { target: { value: "https://example.com/logo.png" } });
    fireEvent.change(screen.getByLabelText("Primary shop category (optional)"), { target: { value: category.id } });
    fireEvent.click(screen.getByRole("radio", { name: "Linen" }));
    fireEvent.click(screen.getByRole("button", { name: "Save shop" }));
    expect(await screen.findByText("Your shop settings were saved.")).toBeInTheDocument();
    const call = patches(calls)[0];
    expect(call.path).toMatch(/\/seller\/shop$/);
    expect(JSON.parse(String(call.init?.body))).toEqual({ shop_name: "Woven Studio", description: "Woven by hand", logo_url: "https://example.com/logo.png", shop_category_id: category.id, theme_id: "linen" });
    expect(new Headers(call.init?.headers).get("X-CSRF-Token")).toBe("shop-csrf");
    expect(screen.getByRole("button", { name: "Save shop" })).toBeDisabled();
    cleanup(); renderShop();
    expect(await screen.findByLabelText("Shop name")).toHaveValue("Woven Studio");
    expect(screen.getByRole("radio", { name: "Linen" })).toBeChecked();
    expect(screen.getByLabelText("Primary shop category (optional)")).toHaveValue(category.id);
  });

  it("retains a disabled category, allows clearing optional fields and works with no active categories", async () => {
    const shop = { ...original, shop_category_id: "disabled-category", description: "Story", logo_url: "https://example.com/a.png" };
    const calls = installFetch((_path, init) => json(init?.method === "PATCH" ? { ...shop, ...JSON.parse(String(init.body)) } : shop), "ACTIVE", []);
    renderShop();
    const select = await screen.findByLabelText("Primary shop category (optional)");
    expect(select).toHaveValue("disabled-category");
    expect(screen.getByRole("option", { name: "Current category (no longer available)" })).toBeInTheDocument();
    expect(screen.getByText(/No active categories are available/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: "Clay" }));
    fireEvent.click(screen.getByRole("button", { name: "Save shop" }));
    await screen.findByText("Your shop settings were saved.");
    expect(JSON.parse(String(patches(calls)[0].init?.body)).shop_category_id).toBe("disabled-category");
    fireEvent.change(select, { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Shop description (optional)"), { target: { value: " " } });
    fireEvent.change(screen.getByLabelText("Logo URL (optional)"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save shop" }));
    await screen.findByText("Your shop settings were saved.");
    expect(JSON.parse(String(patches(calls)[1].init?.body))).toMatchObject({ shop_category_id: null, description: null, logo_url: null });
  });

  it("keeps unsaved edits after category validation failure and permits a corrected retry", async () => {
    let fail = true;
    installFetch((_path, init) => {
      if (init?.method === "PATCH") return fail ? json({ code: "CATEGORY_UNAVAILABLE" }, 422) : json({ ...original, ...JSON.parse(String(init.body)) });
      return json(original);
    });
    renderShop();
    fireEvent.change(await screen.findByLabelText("Shop name"), { target: { value: "Keep this name" } });
    fireEvent.change(screen.getByLabelText("Primary shop category (optional)"), { target: { value: category.id } });
    fireEvent.click(screen.getByRole("radio", { name: "Linen" }));
    fireEvent.click(screen.getByRole("button", { name: "Save shop" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This category is no longer available");
    expect(screen.getByLabelText("Shop name")).toHaveValue("Keep this name");
    expect(screen.getByRole("radio", { name: "Linen" })).toBeChecked();
    fail = false;
    fireEvent.change(screen.getByLabelText("Primary shop category (optional)"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Save shop" }));
    expect(await screen.findByText("Your shop settings were saved.")).toBeInTheDocument();
  });

  it("validates blank names and unsafe logo URLs without sending a mutation", async () => {
    const calls = installFetch(() => json(original));
    renderShop();
    const name = await screen.findByLabelText("Shop name");
    fireEvent.change(name, { target: { value: "   " } });
    fireEvent.submit(screen.getByRole("form", { name: "Shop settings" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Check the shop name");
    fireEvent.change(name, { target: { value: "Changed" } });
    fireEvent.change(screen.getByLabelText("Logo URL (optional)"), { target: { value: "https://user:pass@example.com/a" } });
    fireEvent.submit(screen.getByRole("form", { name: "Shop settings" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(patches(calls)).toHaveLength(0);
  });

  it("shows loading and load failure states and retries", async () => {
    let finish: (value: Response) => void = () => {};
    let fail = true;
    installFetch(() => fail ? new Promise<Response>((resolve) => { finish = resolve; }) : json(original));
    renderShop();
    expect(await screen.findByText("Loading your shop…")).toBeInTheDocument();
    finish(json({ code: "ERROR" }, 500));
    expect(await screen.findByRole("alert")).toHaveTextContent("We could not load or save your shop");
    fail = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByLabelText("Shop name")).toHaveValue("Clay Studio");
  });

  it("disables editing and duplicate submissions during a save", async () => {
    let finish: (value: Response) => void = () => {};
    const calls = installFetch((_path, init) => init?.method === "PATCH" ? new Promise<Response>((resolve) => { finish = resolve; }) : json(original));
    renderShop();
    fireEvent.change(await screen.findByLabelText("Shop name"), { target: { value: "New name" } });
    fireEvent.click(screen.getByRole("button", { name: "Save shop" }));
    await waitFor(() => expect(patches(calls)).toHaveLength(1));
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
    expect(screen.getByLabelText("Shop name")).toBeDisabled();
    fireEvent.submit(screen.getByRole("form", { name: "Shop settings" }));
    expect(patches(calls)).toHaveLength(1);
    finish(json({ ...original, shop_name: "New name" }));
    expect(await screen.findByText("Your shop settings were saved.")).toBeInTheDocument();
  });

  it("blocks further edits if approval is revoked while saving", async () => {
    installFetch((_path, init) => init?.method === "PATCH" ? json({ code: "SELLER_NOT_ACTIVE" }, 403) : json(original));
    renderShop();
    fireEvent.click(await screen.findByRole("radio", { name: "Clay" }));
    fireEvent.click(screen.getByRole("button", { name: "Save shop" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("can no longer edit shop settings");
    expect(screen.getByLabelText("Shop name")).toBeDisabled();
    expect(screen.getByRole("link", { name: "View seller status" })).toHaveAttribute("href", "/seller/onboarding");
  });

  it.each(["DRAFT", "PENDING", "REJECTED", "SUSPENDED"])("redirects %s sellers to onboarding without requesting shop settings", async (status) => {
    const calls = installFetch(() => json(original), status);
    renderShop();
    await screen.findByRole("heading", { name: "Complete your store profile" });
    expect(window.location.pathname).toBe("/seller/onboarding");
    expect(calls.some((call) => call.path.endsWith("/seller/shop"))).toBe(false);
  });

  it("provides product management and public shop destinations", async () => {
    installFetch(() => json(original));
    renderShop();
    await screen.findByLabelText("Shop name");
    expect(screen.getByRole("link", { name: "Manage products" })).toHaveAttribute("href", "/seller/products");
    expect(screen.getByRole("link", { name: "Add product" })).toHaveAttribute("href", "/seller/products/new");
    fireEvent.click(screen.getByRole("link", { name: "View shop" }));
    expect(window.location.pathname).toBe("/shops/shop-1");
    expect(await screen.findByRole("heading", { name: "Clay Studio" })).toBeInTheDocument();
  });

  it("supports Persian RTL and falls back when a logo fails to load", async () => {
    await i18n.changeLanguage("fa");
    installFetch(() => json({ ...original, logo_url: "https://example.com/broken.png" }));
    renderShop();
    expect(await screen.findByLabelText("نام فروشگاه")).toHaveValue("Clay Studio");
    expect(document.documentElement.dir).toBe("rtl");
    fireEvent.click(screen.getByRole("radio", { name: "سفال" }));
    expect(screen.getByRole("radio", { name: "سفال" })).toBeChecked();
    expect(screen.getByRole("button", { name: "ذخیره فروشگاه" })).toBeEnabled();
    fireEvent.error(screen.getByRole("img", { name: "لوگوی Clay Studio" }));
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });
});
