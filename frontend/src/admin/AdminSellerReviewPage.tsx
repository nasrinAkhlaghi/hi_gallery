import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  ApiError,
  approveAdminSeller,
  getAdminSeller,
  getAdminSellers,
  rejectAdminSeller,
  type AdminSellerDetail,
  type AdminSellerStatus,
} from "../auth/api";

const pageSize = 20;
const statuses: AdminSellerStatus[] = ["PENDING", "DRAFT", "ACTIVE", "REJECTED", "SUSPENDED"];

function statusTranslation(status: AdminSellerStatus, t: (key: string) => string) {
  return t(`adminReview.status.${status.toLowerCase()}`);
}

function dateLabel(value: string | null, locale: string, unavailable: string) {
  if (!value) return unavailable;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? unavailable : new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function errorKey(error: unknown) {
  if (error instanceof ApiError && error.status === 409) return "adminReview.conflict";
  if (error instanceof ApiError && error.status === 404) return "adminReview.notFound";
  return "adminReview.loadError";
}

export function AdminSellerListPage() {
  const { t, i18n } = useTranslation();
  const [sellerStatus, setSellerStatus] = useState<AdminSellerStatus>("PENDING");
  const [page, setPage] = useState(0);
  const [data, setData] = useState<Awaited<ReturnType<typeof getAdminSellers>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setData(await getAdminSellers(sellerStatus, page, pageSize));
    } catch (caught) {
      setError(errorKey(caught));
    } finally {
      setLoading(false);
    }
  }, [sellerStatus, page]);

  useEffect(() => { void load(); }, [load]);
  const items = Array.isArray(data?.items) ? data.items : [];
  const total = typeof data?.total === "number" ? data.total : 0;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <main className="mx-auto max-w-6xl px-5 py-8 sm:px-8 lg:py-12">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.18em] text-primary">{t("adminReview.eyebrow")}</p>
          <h2 className="mt-2 font-display text-3xl sm:text-4xl">{t("adminReview.listTitle")}</h2>
        </div>
        <label className="grid gap-1 text-sm">
          <span>{t("adminReview.filterLabel")}</span>
          <select
            value={sellerStatus}
            onChange={(event) => { setSellerStatus(event.target.value as AdminSellerStatus); setPage(0); }}
            className="min-h-11 min-w-48 rounded-lg border border-border bg-background px-3"
          >
            {statuses.map((status) => <option key={status} value={status}>{statusTranslation(status, t)}</option>)}
          </select>
        </label>
      </header>

      {error && <p className="mt-6 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{t(error)}</p>}
      {loading ? <p className="mt-8 text-sm text-muted-foreground" role="status">{t("adminReview.loading")}</p> : !error && data && (
        <>
          {items.length === 0 ? (
            <p className="mt-8 rounded-xl border border-border p-6 text-sm text-muted-foreground" role="status">{t("adminReview.empty")}</p>
          ) : (
            <ul className="mt-7 grid gap-3">
              {items.map((seller) => (
                <li key={seller.seller_id} className="rounded-xl border border-border bg-background p-4 sm:flex sm:items-center sm:justify-between sm:gap-6 sm:p-5">
                  <div className="min-w-0">
                    <Link className="font-medium text-primary underline-offset-4 hover:underline" to={`/admin/sellers/${seller.seller_id}`}>{seller.shop_name}</Link>
                    <p className="mt-1 break-all text-xs text-muted-foreground">{seller.seller_id}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-sm sm:mt-0">
                    <span className="rounded-full bg-muted px-3 py-1">{statusTranslation(seller.seller_status, t)}</span>
                    <span className="text-muted-foreground">{t("adminReview.submittedAt")}: {dateLabel(seller.submitted_at, i18n.language, t("adminReview.unavailable"))}</span>
                    <Link className="min-h-11 inline-flex items-center text-primary underline-offset-4 hover:underline" to={`/admin/sellers/${seller.seller_id}`}>{t("adminReview.viewDetails")}</Link>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <nav className="mt-6 flex flex-wrap items-center justify-between gap-3" aria-label={t("adminReview.paginationLabel")}>
            <button type="button" disabled={page <= 0 || loading} onClick={() => setPage((current) => Math.max(0, current - 1))} className="min-h-11 rounded-full border border-border px-4 disabled:opacity-50">{t("adminReview.previous")}</button>
            <span className="text-sm text-muted-foreground" aria-live="polite">{t("adminReview.page", { current: page + 1, total: pageCount })}</span>
            <button type="button" disabled={page + 1 >= pageCount || loading} onClick={() => setPage((current) => current + 1)} className="min-h-11 rounded-full border border-border px-4 disabled:opacity-50">{t("adminReview.next")}</button>
          </nav>
        </>
      )}
    </main>
  );
}

export function AdminSellerDetailPage() {
  const { t, i18n } = useTranslation();
  const { sellerId = "" } = useParams();
  const [seller, setSeller] = useState<AdminSellerDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [decision, setDecision] = useState<"approve" | "reject" | null>(null);
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");

  const load = useCallback(async (preserveError = false) => {
    if (!preserveError) setError("");
    try {
      setSeller(await getAdminSeller(sellerId));
    } catch (caught) {
      setSeller(null);
      setError(errorKey(caught));
    } finally {
      setLoading(false);
    }
  }, [sellerId]);

  useEffect(() => { void load(); }, [load]);

  async function approve() {
    setBusy(true);
    setError("");
    try {
      await approveAdminSeller(sellerId);
      setNotice("adminReview.approved");
      setDecision(null);
      await load();
    } catch (caught) {
      setError(errorKey(caught));
      if (caught instanceof ApiError && caught.status === 409) await load(true);
    } finally {
      setBusy(false);
    }
  }

  async function reject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedReason = reason.trim();
    if (!trimmedReason) {
      setReasonError("adminReview.reasonRequired");
      return;
    }
    if (trimmedReason.length > 2000) {
      setReasonError("adminReview.reasonTooLong");
      return;
    }
    setReasonError("");
    setBusy(true);
    setError("");
    try {
      await rejectAdminSeller(sellerId, trimmedReason);
      setNotice("adminReview.rejected");
      setDecision(null);
      setReason("");
      await load();
    } catch (caught) {
      setError(errorKey(caught));
      if (caught instanceof ApiError && caught.status === 409) await load(true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-5 py-8 sm:px-8 lg:py-12">
      <Link to="/admin/sellers" className="text-sm text-primary underline-offset-4 hover:underline">{t("adminReview.backToList")}</Link>
      {loading ? <p className="mt-8 text-sm text-muted-foreground" role="status">{t("adminReview.loading")}</p> : error && !seller ? (
        <p className="mt-8 rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive" role="alert">{t(error)}</p>
      ) : seller && (
        <>
          <header className="mt-6 flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-primary">{t("adminReview.eyebrow")}</p>
              <h2 className="mt-2 break-words font-display text-3xl sm:text-4xl">{seller.shop_name}</h2>
              <p className="mt-2 text-sm text-muted-foreground">{t("adminReview.statusLabel")}: {statusTranslation(seller.seller_status, t)}</p>
            </div>
            {seller.seller_status === "PENDING" && <div className="flex flex-wrap gap-2">
              <button type="button" disabled={busy} onClick={() => setDecision("approve")} className="min-h-11 rounded-full bg-primary px-5 text-sm text-primary-foreground disabled:opacity-50">{t("adminReview.approve")}</button>
              <button type="button" disabled={busy} onClick={() => { setDecision("reject"); setReasonError(""); }} className="min-h-11 rounded-full border border-destructive px-5 text-sm text-destructive disabled:opacity-50">{t("adminReview.reject")}</button>
            </div>}
          </header>

          {error && <p className="mt-5 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{t(error)}</p>}
          {notice && <p className="mt-5 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm" role="status">{t(notice)}</p>}

          {decision === "approve" && <section className="mt-6 rounded-xl border border-primary/30 bg-primary/5 p-4" role="dialog" aria-modal="true" aria-labelledby="approve-confirm-title">
            <h3 id="approve-confirm-title" className="font-medium">{t("adminReview.approveConfirmTitle")}</h3>
            <p className="mt-2 text-sm text-muted-foreground">{t("adminReview.approveConfirmDescription")}</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="button" disabled={busy} onClick={() => void approve()} className="min-h-11 rounded-full bg-primary px-4 text-sm text-primary-foreground disabled:opacity-50">{busy ? t("adminReview.processing") : t("adminReview.confirmApprove")}</button>
              <button type="button" disabled={busy} onClick={() => setDecision(null)} className="min-h-11 rounded-full border border-border px-4 text-sm">{t("adminReview.cancel")}</button>
            </div>
          </section>}

          {decision === "reject" && <form className="mt-6 rounded-xl border border-destructive/30 bg-destructive/5 p-4" onSubmit={reject} aria-labelledby="reject-form-title">
            <h3 id="reject-form-title" className="font-medium">{t("adminReview.rejectConfirmTitle")}</h3>
            <label className="mt-4 grid gap-2 text-sm">
              <span>{t("adminReview.reasonLabel")}</span>
              <textarea autoFocus aria-required="true" maxLength={2000} rows={4} value={reason} onChange={(event) => setReason(event.target.value)} aria-invalid={Boolean(reasonError)} aria-describedby={reasonError ? "rejection-reason-error" : undefined} className="w-full rounded-lg border border-border bg-background px-3 py-2" />
            </label>
            {reasonError && <p id="rejection-reason-error" className="mt-2 text-sm text-destructive" role="alert">{t(reasonError)}</p>}
            <div className="mt-4 flex flex-wrap gap-3">
              <button type="submit" disabled={busy} className="min-h-11 rounded-full bg-destructive px-4 text-sm text-destructive-foreground disabled:opacity-50">{busy ? t("adminReview.processing") : t("adminReview.confirmReject")}</button>
              <button type="button" disabled={busy} onClick={() => setDecision(null)} className="min-h-11 rounded-full border border-border px-4 text-sm">{t("adminReview.cancel")}</button>
            </div>
          </form>}

          <section className="mt-7 grid gap-5 rounded-2xl border border-border bg-background p-5 sm:p-7">
            <h3 className="font-display text-xl">{t("adminReview.profileTitle")}</h3>
            {seller.logo_url && <img src={seller.logo_url} alt={t("adminReview.logoAlt", { shop: seller.shop_name })} className="h-24 w-24 rounded-xl border border-border object-cover" />}
            <div><h4 className="text-sm font-medium">{t("adminReview.descriptionLabel")}</h4><p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{seller.description || t("adminReview.noDescription")}</p></div>
            <dl className="grid gap-3 text-sm sm:grid-cols-2"><div><dt className="text-muted-foreground">{t("adminReview.createdAt")}</dt><dd className="mt-1">{dateLabel(seller.created_at, i18n.language, t("adminReview.unavailable"))}</dd></div><div><dt className="text-muted-foreground">{t("adminReview.updatedAt")}</dt><dd className="mt-1">{dateLabel(seller.updated_at, i18n.language, t("adminReview.unavailable"))}</dd></div></dl>
          </section>

          <section className="mt-7">
            <h3 className="font-display text-xl">{t("adminReview.historyTitle")}</h3>
            {seller.history.length === 0 ? <p className="mt-3 text-sm text-muted-foreground">{t("adminReview.noHistory")}</p> : <ol className="mt-4 space-y-3">
              {seller.history.map((event, index) => <li key={`${event.timestamp}-${index}`} className="rounded-xl border border-border bg-background p-4">
                <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{event.previous_status ? statusTranslation(event.previous_status as AdminSellerStatus, t) : t("adminReview.noPreviousStatus")} → {statusTranslation(event.new_status as AdminSellerStatus, t)}</p><time className="text-xs text-muted-foreground">{dateLabel(event.timestamp, i18n.language, t("adminReview.unavailable"))}</time></div>
                <p className="mt-1 text-sm text-muted-foreground">{t(`adminReview.actor.${event.actor_type.toLowerCase()}`)}{event.actor_name ? ` · ${event.actor_name}` : ""}</p>
                {event.reason && <p className="mt-2 whitespace-pre-wrap text-sm">{t("adminReview.reasonLabel")}: {event.reason}</p>}
              </li>)}
            </ol>}
          </section>
        </>
      )}
    </main>
  );
}
