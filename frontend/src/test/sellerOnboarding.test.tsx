import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import i18n from "../i18n";

const sellerUser = { id: "account-id", email: "maker@example.com", roles: ["SELLER"], seller_status: "DRAFT" };
const draftProfile = {
  id: "seller-id",
  shop_name: "Clay Studio",
  description: null,
  logo_url: null,
  status: "DRAFT",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-01T00:00:00Z",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function installFetch(handler: (path: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => handler(String(input), init)));
}

function renderOnboarding() {
  window.history.replaceState(null, "", "/seller/onboarding");
  return render(<App />);
}

beforeEach(async () => {
  cleanup();
  window.localStorage.clear();
  await i18n.changeLanguage("en");
});

afterEach(cleanup);

describe("seller onboarding", () => {
  it("routes a newly registered seller through sign-in to the draft onboarding page", async () => {
    let authenticated = false;
    installFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-value" });
      if (path.endsWith("/auth/register/seller")) return json(sellerUser, 201);
      if (path.endsWith("/auth/login")) {
        authenticated = true;
        return json(sellerUser);
      }
      if (path.endsWith("/auth/me")) return authenticated ? json(sellerUser) : json({ code: "AUTHENTICATION_REQUIRED" }, 401);
      if (path.endsWith("/auth/refresh")) return json({ code: "REFRESH_TOKEN_INVALID" }, 401);
      if (path.endsWith("/seller/profile")) return json(draftProfile);
      if (path.endsWith("/seller/application")) return json({ status: "DRAFT", can_edit: true, can_submit: true });
      return json({ code: "NOT_FOUND" }, 404);
    });
    window.history.replaceState(null, "", "/register/seller");
    render(<App />);
    fireEvent.change(await screen.findByRole("textbox", { name: "Email address" }), { target: { value: "maker@example.com" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Shop name" }), { target: { value: "Clay Studio" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "correct-horse-12" } });
    fireEvent.click(screen.getByRole("button", { name: "Create seller account" }));
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/login");
    fireEvent.change(screen.getByRole("textbox", { name: "Email address" }), { target: { value: "maker@example.com" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "correct-horse-12" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("heading", { name: "Complete your store profile" })).toBeInTheDocument();
    expect(window.location.pathname).toBe("/seller/onboarding");
  });

  it("loads, saves, confirms, and submits a draft profile, then refreshes auth status", async () => {
    let status = "DRAFT";
    let profile = { ...draftProfile };
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    installFetch((path, init) => {
      calls.push({ path, init });
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-value" });
      if (path.endsWith("/auth/me")) return json({ ...sellerUser, seller_status: status });
      if (path.endsWith("/seller/profile") && init?.method === "PATCH") {
        const body = JSON.parse(String(init.body)) as typeof profile;
        profile = { ...profile, ...body };
        return json(profile);
      }
      if (path.endsWith("/seller/profile")) return json(profile);
      if (path.endsWith("/seller/application/submit")) {
        status = "PENDING";
        profile = { ...profile, status };
        return json({ status, can_edit: false, can_submit: false });
      }
      if (path.endsWith("/seller/application")) return json({ status, can_edit: status === "DRAFT", can_submit: status === "DRAFT" });
      return json({ code: "NOT_FOUND" }, 404);
    });

    renderOnboarding();
    expect(await screen.findByRole("heading", { name: "Complete your store profile" })).toBeInTheDocument();
    expect(screen.getByText("Application status: Draft")).toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "Store description (optional)" }), { target: { value: "Handmade in Tehran" } });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
    expect(await screen.findByText("Your store profile was saved.")).toBeInTheDocument();
    const patchCall = calls.find((call) => call.path.endsWith("/seller/profile") && call.init?.method === "PATCH");
    expect(JSON.parse(String(patchCall?.init?.body))).toMatchObject({ description: "Handmade in Tehran", shop_name: "Clay Studio" });

    fireEvent.click(screen.getByRole("button", { name: "Submit for Review" }));
    expect(screen.getByText("Submit this store profile for review?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Confirm submission" }));
    expect(await screen.findByText("Your application was submitted for review.")).toBeInTheDocument();
    expect(screen.getByText("Application status: In review")).toBeInTheDocument();
    expect(calls.some((call) => call.path.endsWith("/seller/application/submit"))).toBe(true);
    expect(calls.filter((call) => call.path.endsWith("/auth/me")).length).toBeGreaterThan(1);
    expect(calls.every((call) => call.init?.credentials === "include")).toBe(true);
  });

  it("shows server validation feedback for a failed profile save", async () => {
    installFetch((path, init) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-value" });
      if (path.endsWith("/auth/me")) return json(sellerUser);
      if (path.endsWith("/seller/profile") && init?.method === "PATCH") return json({ code: "VALIDATION_ERROR" }, 422);
      if (path.endsWith("/seller/profile")) return json(draftProfile);
      if (path.endsWith("/seller/application")) return json({ status: "DRAFT", can_edit: true, can_submit: true });
      return json({ code: "NOT_FOUND" }, 404);
    });
    renderOnboarding();
    fireEvent.change(await screen.findByRole("textbox", { name: "Shop name" }), { target: { value: "Updated Studio" } });
    fireEvent.click(screen.getByRole("button", { name: "Save profile" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Check the shop name and optional logo URL, then try again.");
  });

  it("refreshes status after a submission conflict", async () => {
    let status = "DRAFT";
    installFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-value" });
      if (path.endsWith("/auth/me")) return json({ ...sellerUser, seller_status: status });
      if (path.endsWith("/seller/profile")) return json({ ...draftProfile, status });
      if (path.endsWith("/seller/application/submit")) {
        status = "PENDING";
        return json({ code: "INVALID_APPLICATION_TRANSITION" }, 409);
      }
      if (path.endsWith("/seller/application")) {
        return json({ status, can_edit: status === "DRAFT", can_submit: status === "DRAFT" });
      }
      return json({ code: "NOT_FOUND" }, 404);
    });
    renderOnboarding();
    fireEvent.click(await screen.findByRole("button", { name: "Submit for Review" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm submission" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Your application changed before this action completed.");
    await waitFor(() => expect(screen.getByText("Application status: In review")).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: "Submit for Review" })).not.toBeInTheDocument();
  });

  it("shows pending sellers a distinct read-only status, without approved tools", async () => {
    installFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-value" });
      if (path.endsWith("/auth/me")) return json({ ...sellerUser, seller_status: "PENDING" });
      if (path.endsWith("/seller/profile")) return json({ ...draftProfile, status: "PENDING" });
      if (path.endsWith("/seller/application")) return json({ status: "PENDING", can_edit: false, can_submit: false });
      return json({ code: "NOT_FOUND" }, 404);
    });
    renderOnboarding();
    expect(await screen.findByText("Application status: In review")).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Shop name" })).toHaveAttribute("readonly");
    expect(screen.queryByRole("button", { name: "Save profile" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit for Review" })).not.toBeInTheDocument();
    expect(screen.queryByText("Your seller account is awaiting approval.")).not.toBeInTheDocument();
  });

  it("supports Persian RTL in the onboarding layout and translated form", async () => {
    installFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-value" });
      if (path.endsWith("/auth/me")) return json(sellerUser);
      if (path.endsWith("/seller/profile")) return json(draftProfile);
      if (path.endsWith("/seller/application")) return json({ status: "DRAFT", can_edit: true, can_submit: true });
      return json({ code: "NOT_FOUND" }, 404);
    });
    renderOnboarding();
    await screen.findByRole("heading", { name: "Complete your store profile" });
    fireEvent.change(screen.getAllByRole("combobox", { name: "Select language" })[0], { target: { value: "fa" } });
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(document.documentElement.lang).toBe("fa");
    expect(await screen.findByRole("heading", { name: "تکمیل پروفایل فروشگاه" })).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "نام فروشگاه" })).toBeInTheDocument();
  });
});
