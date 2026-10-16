import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import i18n from "../i18n";

const sellerId = "seller-0001";
const adminUser = { id: "admin-account", email: "admin@example.com", roles: ["ADMIN"], seller_status: null };
const pendingSeller = {
  seller_id: sellerId,
  shop_name: "Clay Studio",
  description: "Handmade pottery",
  logo_url: "https://example.com/logo.png",
  seller_status: "PENDING",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2025-01-02T00:00:00Z",
  history: [
    { previous_status: null, new_status: "DRAFT", action: "SELLER_REGISTERED", timestamp: "2025-01-01T00:00:00Z", actor_type: "SELLER", actor_name: null, reason: null },
    { previous_status: "DRAFT", new_status: "PENDING", action: "APPLICATION_SUBMITTED", timestamp: "2025-01-02T00:00:00Z", actor_type: "SELLER", actor_name: null, reason: null },
  ],
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function installFetch(handler: (path: string, init?: RequestInit) => Response | Promise<Response>) {
  vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL, init?: RequestInit) => handler(String(input), init)));
}

function renderAt(path: string) {
  window.history.replaceState(null, "", path);
  return render(<App />);
}

function authResponse(path: string): Response | undefined {
  if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-value" });
  if (path.endsWith("/auth/me")) return json(adminUser);
  return undefined;
}

beforeEach(async () => {
  cleanup();
  window.localStorage.clear();
  await i18n.changeLanguage("en");
  window.history.replaceState(null, "", "/");
});

afterEach(cleanup);

describe("admin seller review", () => {
  it("loads the pending queue, filters statuses, and paginates", async () => {
    const calls: string[] = [];
    installFetch((path) => {
      calls.push(path);
      const auth = authResponse(path);
      if (auth) return auth;
      if (path.includes("/admin/sellers?")) {
        const status = new URL(path, "http://localhost").searchParams.get("status");
        const page = Number(new URL(path, "http://localhost").searchParams.get("page"));
        return json({
          items: [{ ...pendingSeller, seller_status: status, submitted_at: "2025-01-02T00:00:00Z" }],
          total: status === "PENDING" ? 21 : 1,
          page,
          page_size: 20,
        });
      }
      return json({ code: "NOT_FOUND" }, 404);
    });

    renderAt("/admin/sellers");
    expect(await screen.findByRole("heading", { name: "Seller applications" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Clay Studio" })).toHaveAttribute("href", `/admin/sellers/${sellerId}`);
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(calls.some((call) => call.includes("page=1"))).toBe(true));
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("combobox", { name: "Filter by status" }), { target: { value: "DRAFT" } });
    await waitFor(() => expect(calls.some((call) => call.includes("status=DRAFT"))).toBe(true));
    expect(screen.getAllByText("Draft").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("shows seller details and requires confirmation before approval", async () => {
    let sellerStatus = "PENDING";
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    installFetch((path, init) => {
      calls.push({ path, init });
      const auth = authResponse(path);
      if (auth) return auth;
      if (path.endsWith(`/admin/sellers/${sellerId}/approve`)) {
        sellerStatus = "ACTIVE";
        return json({ seller_id: sellerId, seller_status: sellerStatus, decided_at: "2025-01-03T00:00:00Z" });
      }
      if (path.endsWith(`/admin/sellers/${sellerId}`)) {
        return json({ ...pendingSeller, seller_status: sellerStatus, history: sellerStatus === "ACTIVE" ? [
          ...pendingSeller.history,
          { previous_status: "PENDING", new_status: "ACTIVE", action: "APPLICATION_APPROVED", timestamp: "2025-01-03T00:00:00Z", actor_type: "ADMIN", actor_name: "Review Admin", reason: null },
        ] : pendingSeller.history });
      }
      return json({ code: "NOT_FOUND" }, 404);
    });

    renderAt(`/admin/sellers/${sellerId}`);
    expect(await screen.findByRole("heading", { name: "Clay Studio" })).toBeInTheDocument();
    expect(screen.getByText("Handmade pottery")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Application history" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    expect(screen.getByRole("dialog", { name: "Approve this seller application?" })).toBeInTheDocument();
    expect(calls.some((call) => call.path.endsWith("/approve"))).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Confirm approval" }));
    expect(await screen.findByText("The seller application was approved.")).toBeInTheDocument();
    expect(screen.getByText("Status: Approved")).toBeInTheDocument();
    expect(calls.some((call) => call.path.endsWith("/approve") && call.init?.method === "POST")).toBe(true);
    expect(calls.every((call) => call.init?.credentials === "include")).toBe(true);
  });

  it("validates rejection reason and submits the required reason", async () => {
    let sellerStatus = "PENDING";
    let rejectionReason: string | null = null;
    let detailReads = 0;
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    installFetch((path, init) => {
      calls.push({ path, init });
      const auth = authResponse(path);
      if (auth) return auth;
      if (path.endsWith(`/admin/sellers/${sellerId}/reject`)) {
        rejectionReason = (JSON.parse(String(init?.body)) as { reason: string }).reason;
        sellerStatus = "REJECTED";
        return json({ seller_id: sellerId, seller_status: sellerStatus, decided_at: "2025-01-03T00:00:00Z" });
      }
      if (path.endsWith(`/admin/sellers/${sellerId}`)) {
        detailReads += 1;
        return json({ ...pendingSeller, seller_status: sellerStatus, history: sellerStatus === "REJECTED" ? [
          ...pendingSeller.history,
          { previous_status: "PENDING", new_status: "REJECTED", action: "APPLICATION_REJECTED", timestamp: "2025-01-03T00:00:00Z", actor_type: "ADMIN", actor_name: "Review Admin", reason: rejectionReason },
        ] : pendingSeller.history });
      }
      return json({ code: "NOT_FOUND" }, 404);
    });

    renderAt(`/admin/sellers/${sellerId}`);
    fireEvent.click(await screen.findByRole("button", { name: "Reject" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm rejection" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter a reason before rejecting this application.");
    fireEvent.change(screen.getByRole("textbox", { name: "Rejection reason" }), { target: { value: "  Add clearer product photographs.  " } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm rejection" }));
    expect(await screen.findByText("The seller application was rejected.")).toBeInTheDocument();
    expect(screen.getByText("Status: Rejected")).toBeInTheDocument();
    expect(screen.getByText(/Add clearer product photographs\./)).toBeInTheDocument();
    const rejectCall = calls.find((call) => call.path.endsWith("/reject"));
    expect(JSON.parse(String(rejectCall?.init?.body))).toEqual({ reason: "Add clearer product photographs." });
    expect(detailReads).toBeGreaterThan(1);
  });

  it("refreshes authoritative details and explains a stale decision conflict", async () => {
    let sellerStatus = "PENDING";
    installFetch((path) => {
      const auth = authResponse(path);
      if (auth) return auth;
      if (path.endsWith(`/admin/sellers/${sellerId}/approve`)) {
        sellerStatus = "ACTIVE";
        return json({ code: "SELLER_DECISION_CONFLICT" }, 409);
      }
      if (path.endsWith(`/admin/sellers/${sellerId}`)) return json({ ...pendingSeller, seller_status: sellerStatus });
      return json({ code: "NOT_FOUND" }, 404);
    });
    renderAt(`/admin/sellers/${sellerId}`);
    fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm approval" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("This application changed before your decision was saved.");
    await waitFor(() => expect(screen.getByText("Status: Approved")).toBeInTheDocument());
  });

  it("shows seller rejection feedback without offering resubmission", async () => {
    const seller = { id: "seller-account", email: "maker@example.com", roles: ["SELLER"], seller_status: "REJECTED" };
    installFetch((path) => {
      if (path.endsWith("/auth/csrf")) return json({ csrf_token: "csrf-value" });
      if (path.endsWith("/auth/me")) return json(seller);
      if (path.endsWith("/seller/profile")) return json({ ...pendingSeller, id: sellerId, status: "REJECTED" });
      if (path.endsWith("/seller/application")) return json({ status: "REJECTED", can_edit: false, can_submit: false, rejection_reason: "Add clear product photos." });
      return json({ code: "NOT_FOUND" }, 404);
    });
    renderAt("/seller/onboarding");
    expect(await screen.findByText("This application was rejected. Editing and resubmission will be handled in a later phase.")).toBeInTheDocument();
    expect(screen.getByText("Reason for the decision")).toBeInTheDocument();
    expect(screen.getByText("Add clear product photos.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit for Review" })).not.toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Shop name" })).toHaveAttribute("readonly");
  });

  it("renders review screens in Persian RTL", async () => {
    installFetch((path) => {
      const auth = authResponse(path);
      if (auth) return auth;
      if (path.includes("/admin/sellers?")) return json({ items: [], total: 0, page: 0, page_size: 20 });
      return json({ code: "NOT_FOUND" }, 404);
    });
    renderAt("/admin/sellers");
    await screen.findByRole("heading", { name: "Seller applications" });
    fireEvent.change(screen.getAllByRole("combobox", { name: "Select language" })[0], { target: { value: "fa" } });
    await waitFor(() => expect(document.documentElement.dir).toBe("rtl"));
    expect(document.documentElement.lang).toBe("fa");
    expect(await screen.findByRole("heading", { name: "درخواست‌های فروشندگی" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "فیلتر بر اساس وضعیت" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "صفحه‌های درخواست فروشندگی" })).toBeInTheDocument();
  });
});
