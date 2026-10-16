import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import i18n from "../i18n";
import { apiRequest } from "../auth/api";

const user = { id: "user-id", email: "maker@example.com", roles: ["BUYER"], seller_status: null };

function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function mockFetch(handler: (path: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => handler(String(input), init)));
}

beforeEach(async () => {
  cleanup();
  await i18n.changeLanguage("en");
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  cleanup();
});

describe("frontend authentication", () => {
  it("validates and submits login credentials, stores only in-memory user state, and supports localized RTL", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    mockFetch((path, init) => {
      calls.push({ path, init });
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-before-login" });
      if (path.endsWith("/auth/login")) return json(user);
      if (path.endsWith("/auth/me") || path.endsWith("/auth/refresh")) return json({ code: "AUTHENTICATION_REQUIRED" }, 401);
      return json({}, 404);
    });

    window.history.replaceState(null, "", "/login");
    render(<App />);
    const email = await screen.findByRole("textbox", { name: "Email address" });
    const password = screen.getByLabelText(/Password/);
    expect(email).toBeRequired();
    expect(password).toBeRequired();
    fireEvent.change(email, { target: { value: "maker@example.com" } });
    fireEvent.change(password, { target: { value: "correct-horse-12" } });
    fireEvent.change(screen.getByRole("combobox", { name: "Select language" }), { target: { value: "fa" } });
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    fireEvent.click(screen.getByRole("button", { name: "ورود" }));

    expect(await screen.findByRole("heading", { name: "پروفایل" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("fa");
    expect(window.localStorage.getItem("hi-gallery-language")).toBe("fa");
    const loginCall = calls.find((call) => call.path.endsWith("/auth/login"));
    expect(loginCall?.init?.credentials).toBe("include");
    expect(new Headers(loginCall?.init?.headers).get("X-CSRF-Token")).toBe("csrf-before-login");
    expect(calls.slice(0, calls.indexOf(loginCall!)).filter((call) => call.path.endsWith("/auth/csrf"))).toHaveLength(2);
    expect(window.localStorage.getItem("access_token")).toBeNull();
  });

  it("shows a localized generic credential error for failed login", async () => {
    mockFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/auth/login")) return json({ code: "INVALID_CREDENTIALS", message: "Invalid credentials" }, 401);
      return json({}, 401);
    });
    window.history.replaceState(null, "", "/login");
    render(<App />);
    fireEvent.change(await screen.findByRole("textbox", { name: "Email address" }), { target: { value: "x@example.com" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Email or password is incorrect.");
  });

  it("submits seller registration to the documented seller endpoint", async () => {
    let submittedPath = "";
    let submittedBody = "";
    mockFetch((path, init) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/auth/register/seller")) {
        submittedPath = path;
        submittedBody = String(init?.body);
        return json({ ...user, roles: ["SELLER"], seller_status: "PENDING" }, 201);
      }
      return json({}, 401);
    });
    window.history.replaceState(null, "", "/register/seller");
    render(<App />);
    fireEvent.change(await screen.findByRole("textbox", { name: "Email address" }), { target: { value: "maker@example.com" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Shop name" }), { target: { value: "Clay Studio" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "correct-horse-12" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit seller registration" }));
    expect(await screen.findByText("Your account was created. Sign in to continue.")).toBeInTheDocument();
    expect(submittedPath).toContain("/auth/register/seller");
    expect(JSON.parse(submittedBody)).toMatchObject({ shop_name: "Clay Studio" });
  });

  it("submits buyer registration and routes the user to sign-in", async () => {
    let submittedPath = "";
    mockFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/auth/register")) {
        submittedPath = path;
        return json(user, 201);
      }
      return json({}, 401);
    });
    window.history.replaceState(null, "", "/register");
    render(<App />);
    fireEvent.change(await screen.findByRole("textbox", { name: "Email address" }), { target: { value: "buyer@example.com" } });
    fireEvent.change(screen.getByRole("textbox", { name: "Your name" }), { target: { value: "Buyer Name" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "correct-horse-12" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Your account was created. Sign in to continue.")).toBeInTheDocument();
    expect(submittedPath).toContain("/auth/register");
  });

  it("logs out through the CSRF-protected API and clears current-user state", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    mockFetch((path, init) => {
      calls.push({ path, init });
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/auth/me")) return json(user);
      if (path.endsWith("/auth/logout")) return json(null, 204);
      return json({}, 401);
    });
    render(<App />);
    const signOutButtons = await screen.findAllByRole("button", { name: "Sign out" });
    fireEvent.click(signOutButtons[0]);
    expect(await screen.findAllByRole("link", { name: "Sign in" })).not.toHaveLength(0);
    const logoutCall = calls.find((call) => call.path.endsWith("/auth/logout"));
    expect(new Headers(logoutCall?.init?.headers).get("X-CSRF-Token")).toBe("csrf");
    expect(logoutCall?.init?.credentials).toBe("include");
  });

  it("redirects unauthenticated users from protected routes to login", async () => {
    mockFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf" });
      return json({ code: "AUTHENTICATION_REQUIRED" }, 401);
    });
    window.history.replaceState(null, "", "/profile");
    render(<App />);
    expect(await screen.findByRole("heading", { name: "Welcome back" })).toBeInTheDocument();
  });

  it("blocks pending sellers and non-admin users from privileged workspace routes", async () => {
    mockFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/auth/me")) return json({ ...user, roles: ["SELLER"], seller_status: "PENDING" });
      return json({}, 401);
    });
    window.history.replaceState(null, "", "/seller");
    render(<App />);
    expect(await screen.findByText("Your seller account is awaiting approval.")).toBeInTheDocument();
  });

  it("deduplicates simultaneous refreshes and retries each original request only once", async () => {
    let refreshCalls = 0;
    let protectedCalls = 0;
    mockFetch(async (path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf" });
      if (path.endsWith("/auth/refresh")) {
        refreshCalls += 1;
        await new Promise((resolve) => setTimeout(resolve, 5));
        return json(user);
      }
      if (path.endsWith("/protected")) {
        protectedCalls += 1;
        return protectedCalls <= 2 ? json({ code: "expired" }, 401) : json({ ok: true });
      }
      return json({}, 404);
    });
    const [first, second] = await Promise.all([
      apiRequest<{ ok: boolean }>("/protected"),
      apiRequest<{ ok: boolean }>("/protected"),
    ]);
    expect(first.ok && second.ok).toBe(true);
    expect(refreshCalls).toBe(1);
    expect(protectedCalls).toBe(4);
  });
});
