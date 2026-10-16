import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import en from "../i18n/locales/en/common.json";
import fa from "../i18n/locales/fa/common.json";
import i18n from "../i18n";
import { BrowserRouter } from "react-router-dom";

const LANGUAGE_STORAGE_KEY = "hi-gallery-language";

function renderAt(path: string) {
  window.history.replaceState(null, "", path);
  return render(<App />);
}

function translationKeys(value: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(value).flatMap(([key, child]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return child !== null && typeof child === "object" && !Array.isArray(child)
      ? translationKeys(child as Record<string, unknown>, path)
      : [path];
  });
}

beforeEach(async () => {
  cleanup();
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
  await i18n.changeLanguage("en");
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
});

describe("language initialization and switching", () => {
  it("defaults to English when no saved preference exists", async () => {
    vi.resetModules();
    const { default: freshI18n } = await import("../i18n");

    expect(freshI18n.resolvedLanguage).toBe("en");
    expect(document.documentElement.lang).toBe("en");
    expect(document.documentElement.dir).toBe("ltr");
  });

  it("persists and restores Persian, including the document direction", async () => {
    await i18n.changeLanguage("fa");

    expect(window.localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe("fa");
    expect(document.documentElement.lang).toBe("fa");
    expect(document.documentElement.dir).toBe("rtl");

    vi.resetModules();
    const { default: restoredI18n } = await import("../i18n");
    expect(restoredI18n.resolvedLanguage).toBe("fa");
    expect(document.documentElement.lang).toBe("fa");
    expect(document.documentElement.dir).toBe("rtl");
  });

  it("updates language immediately without changing the current route", async () => {
    window.history.replaceState(null, "", "/profile");
    render(
      <BrowserRouter>
        <LanguageSwitcher />
      </BrowserRouter>,
    );

    fireEvent.change(screen.getByRole("combobox", { name: "Select language" }), {
      target: { value: "fa" },
    });

    await waitFor(() => expect(document.documentElement.lang).toBe("fa"));
    expect(document.documentElement.dir).toBe("rtl");
    expect(window.location.pathname).toBe("/profile");
    expect(screen.getByRole("combobox", { name: "انتخاب زبان" })).toHaveValue("fa");
  });

  it("keeps both locale bundles synchronized and populated", () => {
    const englishKeys = translationKeys(en).sort();
    const persianKeys = translationKeys(fa).sort();

    expect(persianKeys).toEqual(englishKeys);
    for (const key of englishKeys) {
      const getValue = (bundle: Record<string, unknown>) =>
        key.split(".").reduce<unknown>((value, part) => (value as Record<string, unknown>)[part], bundle);
      expect(getValue(en), `English translation ${key}`).not.toBe("");
      expect(getValue(fa), `Persian translation ${key}`).not.toBe("");
    }
  });
});

describe("route layouts and navigation", () => {
  it.each([
    "/",
    "/browse",
    "/products/sample-id",
    "/categories",
    "/cart",
    "/checkout",
    "/orders",
    "/reviews",
    "/profile",
    "/seller",
    "/seller/onboarding",
    "/seller/products",
    "/seller/orders",
    "/seller/shop",
    "/seller/settings",
    "/admin",
    "/admin/sellers",
    "/admin/buyers",
    "/admin/products",
    "/admin/orders",
    "/admin/reviews",
    "/admin/reports",
  ])("renders the language control on direct route %s", async (path) => {
    renderAt(path);

    const expectedCount = path === "/" || path.startsWith("/seller") || path.startsWith("/admin") ? 2 : 1;
    await screen.findAllByRole("combobox", { name: "Select language" });
    expect(screen.getAllByRole("combobox", { name: "Select language" })).toHaveLength(expectedCount);
  });

  it.each([
    ["/browse", "مرور محصولات", 1],
    ["/seller", "فضای فروشنده", 2],
    ["/admin", "پنل مدیریت", 2],
  ])("restores the selected language on direct entry to %s", async (path, heading, switcherCount) => {
    await i18n.changeLanguage("fa");
    renderAt(path);

    expect(await screen.findByRole("heading", { name: heading })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("fa");
    expect(document.documentElement.dir).toBe("rtl");
    expect(screen.getAllByRole("combobox", { name: "انتخاب زبان" })).toHaveLength(switcherCount);
  });

  it("renders buyer and workspace navigation links that target existing route paths", async () => {
    renderAt("/");

    await screen.findAllByRole("navigation", { name: "Main navigation" });
    const homeNavigation = screen.getAllByRole("navigation", { name: "Main navigation" })[0];
    expect(within(homeNavigation).getByRole("link", { name: "Categories" })).toHaveAttribute("href", "/categories");
    expect(within(homeNavigation).getByRole("link", { name: "Cart" })).toHaveAttribute("href", "/cart");
    expect(within(homeNavigation).getByRole("link", { name: "Orders" })).toHaveAttribute("href", "/orders");
    expect(within(homeNavigation).getByRole("link", { name: "Profile" })).toHaveAttribute("href", "/profile");

    cleanup();
    renderAt("/admin");
    await screen.findByRole("button", { name: "Open Admin Console menu" });
    const adminNavigation = document.querySelector("#admin-mobile-navigation");
    expect(adminNavigation).not.toBeNull();
    for (const route of ["/admin", "/admin/sellers", "/admin/buyers", "/admin/products", "/admin/orders", "/admin/reviews", "/admin/reports"]) {
      expect(adminNavigation?.querySelector(`a[href="${route}"]`)).not.toBeNull();
    }
  });

  it("opens the seller mobile menu and closes it after navigation", async () => {
    renderAt("/seller");

    const menuButton = await screen.findByRole("button", { name: "Open Seller Studio menu" });
    fireEvent.click(menuButton);
    expect(menuButton).toHaveAttribute("aria-expanded", "true");

    const mobileNavigation = document.querySelector("#seller-mobile-navigation");
    expect(mobileNavigation).not.toBeNull();
    fireEvent.click(within(mobileNavigation as HTMLElement).getByRole("link", { name: "Products" }));

    expect(window.location.pathname).toBe("/seller/products");
    await waitFor(() => expect(menuButton).toHaveAttribute("aria-expanded", "false"));
  });

  it("closes the buyer mobile menu when a route link is selected", async () => {
    renderAt("/");

    const menuButton = await screen.findByRole("button", { name: "Open menu" });
    fireEvent.click(menuButton);
    expect(menuButton).toHaveAttribute("aria-expanded", "true");

    const mobileNavigation = document.querySelector("#mobile-buyer-navigation");
    expect(mobileNavigation).not.toBeNull();
    fireEvent.click(within(mobileNavigation as HTMLElement).getByRole("link", { name: "Categories" }));

    expect(window.location.pathname).toBe("/categories");
    expect(await screen.findByRole("heading", { name: "Categories" })).toBeInTheDocument();
  });

  it("keeps the route and closes the seller mobile menu after changing language", async () => {
    renderAt("/seller/orders");

    const menuButton = await screen.findByRole("button", { name: "Open Seller Studio menu" });
    fireEvent.click(menuButton);
    const mobileNavigation = document.querySelector("#seller-mobile-navigation") as HTMLElement;
    fireEvent.change(within(mobileNavigation).getByRole("combobox", { name: "Select language" }), {
      target: { value: "fa" },
    });

    await waitFor(() => expect(menuButton).toHaveAttribute("aria-expanded", "false"));
    expect(window.location.pathname).toBe("/seller/orders");
    expect(document.documentElement.lang).toBe("fa");
    expect(document.documentElement.dir).toBe("rtl");
  });
});
