const apiBase = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const csrfHeader = "X-CSRF-Token";
let csrfToken: string | null = null;
let refreshInFlight: Promise<boolean> | null = null;

export type AuthUser = {
  id: string;
  email: string;
  roles: Array<"BUYER" | "SELLER" | "ADMIN">;
  seller_status: string | null;
};

export type SellerProfile = {
  id: string;
  shop_name: string;
  description: string | null;
  logo_url: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type SellerApplication = {
  status: string;
  can_edit: boolean;
  can_submit: boolean;
  rejection_reason?: string | null;
};

export type AdminSellerStatus = "DRAFT" | "PENDING" | "ACTIVE" | "REJECTED" | "SUSPENDED";

export type AdminSellerListItem = {
  seller_id: string;
  shop_name: string;
  seller_status: AdminSellerStatus;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
};

export type AdminSellerList = {
  items: AdminSellerListItem[];
  total: number;
  page: number;
  page_size: number;
};

export type AdminSellerHistoryItem = {
  previous_status: string | null;
  new_status: string;
  action: string;
  timestamp: string;
  actor_type: "SELLER" | "ADMIN";
  actor_name: string | null;
  reason: string | null;
};

export type AdminSellerDetail = {
  seller_id: string;
  shop_name: string;
  description: string | null;
  logo_url: string | null;
  seller_status: AdminSellerStatus;
  created_at: string;
  updated_at: string;
  history: AdminSellerHistoryItem[];
};

export type AdminSellerDecision = {
  seller_id: string;
  seller_status: AdminSellerStatus;
  decided_at: string;
};

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

async function updateCsrf(): Promise<void> {
  const response = await fetch(`${apiBase}/auth/csrf`, { credentials: "include" });
  if (!response.ok) throw new ApiError(response.status, "CSRF_UNAVAILABLE", "Could not prepare the request.");
  const body = (await response.json()) as { csrf_token: string };
  csrfToken = body.csrf_token;
}

function isMutation(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase());
}

async function rawRequest(path: string, init: RequestInit): Promise<Response> {
  return fetch(`${apiBase}${path}`, { ...init, credentials: "include" });
}

async function refreshSession(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        if (!csrfToken) await updateCsrf();
        const response = await rawRequest("/auth/refresh", {
          method: "POST",
          headers: { [csrfHeader]: csrfToken ?? "" },
        });
        if (!response.ok) {
          csrfToken = null;
          return false;
        }
        await updateCsrf();
        return true;
      } catch {
        csrfToken = null;
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = init.method ?? "GET";
  const headers = new Headers(init.headers);
  if (isMutation(method)) {
    if (!csrfToken) await updateCsrf();
    headers.set(csrfHeader, csrfToken ?? "");
  }
  let response = await rawRequest(path, { ...init, headers });
  const authOperation = ["/auth/login", "/auth/register", "/auth/register/seller", "/auth/refresh", "/auth/logout", "/auth/csrf"].includes(path);
  const mayRefresh = response.status === 401 && !authOperation;
  if (mayRefresh) {
    if (await refreshSession()) {
      const retryHeaders = new Headers(init.headers);
      if (isMutation(method)) retryHeaders.set(csrfHeader, csrfToken ?? "");
      response = await rawRequest(path, { ...init, headers: retryHeaders });
    }
    if (response.status === 401) window.dispatchEvent(new Event("hi-gallery:unauthorized"));
  } else if (response.status === 401) {
    window.dispatchEvent(new Event("hi-gallery:unauthorized"));
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { code?: string; message?: string };
    throw new ApiError(response.status, body.code ?? "REQUEST_FAILED", body.message ?? "Request failed.");
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json() as T;
  if (path === "/auth/csrf" && typeof body === "object" && body !== null && "csrf_token" in body) {
    csrfToken = String((body as { csrf_token: string }).csrf_token);
  }
  return body;
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const user = await apiRequest<AuthUser>("/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
  });
  await updateCsrf();
  return user;
}

export async function registerBuyer(values: { email: string; password: string; display_name: string }): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/register", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values),
  });
}

export async function registerSeller(values: { email: string; password: string; shop_name: string }): Promise<AuthUser> {
  return apiRequest<AuthUser>("/auth/register/seller", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values),
  });
}

export async function getSellerProfile(): Promise<SellerProfile> {
  return apiRequest<SellerProfile>("/seller/profile");
}

export async function updateSellerProfile(values: Pick<SellerProfile, "shop_name" | "description" | "logo_url">): Promise<SellerProfile> {
  return apiRequest<SellerProfile>("/seller/profile", {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values),
  });
}

export async function getSellerApplication(): Promise<SellerApplication> {
  return apiRequest<SellerApplication>("/seller/application");
}

export async function submitSellerApplication(): Promise<SellerApplication> {
  return apiRequest<SellerApplication>("/seller/application/submit", { method: "POST" });
}

export async function getAdminSellers(status: AdminSellerStatus, page: number, pageSize: number): Promise<AdminSellerList> {
  const params = new URLSearchParams({ status, page: String(page), page_size: String(pageSize) });
  return apiRequest<AdminSellerList>(`/admin/sellers?${params.toString()}`);
}

export async function getAdminSeller(sellerId: string): Promise<AdminSellerDetail> {
  return apiRequest<AdminSellerDetail>(`/admin/sellers/${encodeURIComponent(sellerId)}`);
}

export async function approveAdminSeller(sellerId: string): Promise<AdminSellerDecision> {
  return apiRequest<AdminSellerDecision>(`/admin/sellers/${encodeURIComponent(sellerId)}/approve`, { method: "POST" });
}

export async function rejectAdminSeller(sellerId: string, reason: string): Promise<AdminSellerDecision> {
  return apiRequest<AdminSellerDecision>(`/admin/sellers/${encodeURIComponent(sellerId)}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason }),
  });
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<void>("/auth/logout", { method: "POST" });
  } finally {
    csrfToken = null;
  }
}

export function clearCsrfToken(): void {
  csrfToken = null;
}
