import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { ApiError, getSellerApplication, getSellerProfile, submitSellerApplication, updateSellerProfile, type SellerApplication, type SellerProfile } from "../auth/api";
import { useAuth } from "../auth/AuthContext";

type ProfileFields = { shop_name: string; description: string; logo_url: string };

function fieldsFrom(profile: SellerProfile): ProfileFields {
  return {
    shop_name: profile.shop_name,
    description: profile.description ?? "",
    logo_url: profile.logo_url ?? "",
  };
}

function errorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 409) return "sellerOnboarding.conflict";
    if (error.status === 403) return "sellerOnboarding.forbidden";
    if (error.status === 422) return "sellerOnboarding.validationError";
  }
  return "sellerOnboarding.requestError";
}

export function SellerOnboardingPage() {
  const { t } = useTranslation();
  const { reloadUser } = useAuth();
  const [profile, setProfile] = useState<SellerProfile | null>(null);
  const [application, setApplication] = useState<SellerApplication | null>(null);
  const [fields, setFields] = useState<ProfileFields>({ shop_name: "", description: "", logo_url: "" });
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [confirming, setConfirming] = useState(false);

  async function refreshProfile() {
    const [nextProfile, nextApplication] = await Promise.all([getSellerProfile(), getSellerApplication()]);
    setProfile(nextProfile);
    setApplication(nextApplication);
    setFields(fieldsFrom(nextProfile));
  }

  useEffect(() => {
    let active = true;
    void Promise.all([getSellerProfile(), getSellerApplication()])
      .then(([nextProfile, nextApplication]) => {
        if (!active) return;
        setProfile(nextProfile);
        setApplication(nextApplication);
        setFields(fieldsFrom(nextProfile));
      })
      .catch((caught: unknown) => {
        if (active) setError(errorKey(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const isDraft = application?.status === "DRAFT";
  const isDirty = profile !== null && (
    fields.shop_name !== profile.shop_name ||
    fields.description !== (profile.description ?? "") ||
    fields.logo_url !== (profile.logo_url ?? "")
  );

  async function saveProfile(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await updateSellerProfile({
        shop_name: fields.shop_name,
        description: fields.description || null,
        logo_url: fields.logo_url || null,
      });
      setProfile(updated);
      setFields(fieldsFrom(updated));
      setNotice("sellerOnboarding.saved");
    } catch (caught) {
      setError(errorKey(caught));
      if (caught instanceof ApiError && caught.status === 409) {
        try { await refreshProfile(); } catch { /* Keep the conflict message visible. */ }
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitApplication() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const updated = await submitSellerApplication();
      setApplication(updated);
      setProfile((current) => current ? { ...current, status: updated.status } : current);
      await reloadUser();
      setConfirming(false);
      setNotice("sellerOnboarding.submitted");
    } catch (caught) {
      setError(errorKey(caught));
      if (caught instanceof ApiError && caught.status === 409) {
        try { await refreshProfile(); } catch { /* Keep the conflict message visible. */ }
      }
    } finally {
      setBusy(false);
    }
  }

  const status = application?.status ?? profile?.status ?? "DRAFT";
  const statusKey = ["DRAFT", "PENDING", "ACTIVE", "REJECTED", "SUSPENDED"].includes(status)
    ? `sellerOnboarding.status.${status.toLowerCase()}`
    : "sellerOnboarding.status.unknown";

  if (loading) {
    return <main className="mx-auto max-w-5xl px-5 py-12 sm:px-8" role="status">{t("sellerOnboarding.loading")}</main>;
  }

  return (
    <main className="mx-auto max-w-5xl px-5 py-10 sm:px-8">
      <header className="mb-8">
        <p className="text-xs uppercase tracking-[0.18em] text-primary">{t("sellerOnboarding.eyebrow")}</p>
        <h2 className="mt-2 font-display text-3xl sm:text-4xl">{t("sellerOnboarding.title")}</h2>
        {application && <p className="mt-3 text-sm text-muted-foreground" role="status">{t("sellerOnboarding.currentStatus", { status: t(statusKey) })}</p>}
      </header>

      {error && <p role="alert" className="mb-5 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{t(error)}</p>}
      {notice && <p role="status" className="mb-5 rounded-lg border border-primary/30 bg-primary/5 p-3 text-sm">{t(notice)}</p>}
      {!profile || !application ? <p role="alert">{t("sellerOnboarding.requestError")}</p> : (
        <>
          <section className="mb-7 rounded-2xl border border-border bg-background p-5 sm:p-7">
            <h3 className="font-display text-xl">{t("sellerOnboarding.profileTitle")}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{t(isDraft ? "sellerOnboarding.draftIntro" : `sellerOnboarding.statusMessage.${status.toLowerCase()}`)}</p>
            {status === "REJECTED" && application.rejection_reason && <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/5 p-4" role="status">
              <h4 className="font-medium">{t("sellerOnboarding.rejectionReason")}</h4>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{application.rejection_reason}</p>
            </div>}
            <form className="mt-6 space-y-5" onSubmit={saveProfile}>
              <label className="block text-sm font-medium">
                {t("sellerOnboarding.shopName")}
                <input required minLength={1} maxLength={150} value={fields.shop_name} readOnly={!isDraft} onChange={(event) => setFields((current) => ({ ...current, shop_name: event.target.value }))} className="mt-2 min-h-11 w-full rounded-lg border border-border bg-background px-3 read-only:bg-muted" />
              </label>
              <label className="block text-sm font-medium">
                {t("sellerOnboarding.description")}
                <textarea maxLength={10000} rows={4} value={fields.description} readOnly={!isDraft} onChange={(event) => setFields((current) => ({ ...current, description: event.target.value }))} className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 read-only:bg-muted" />
              </label>
              <label className="block text-sm font-medium">
                {t("sellerOnboarding.logoUrl")}
                <input dir="ltr" type="url" maxLength={2048} value={fields.logo_url} readOnly={!isDraft} onChange={(event) => setFields((current) => ({ ...current, logo_url: event.target.value }))} className="mt-2 min-h-11 w-full rounded-lg border border-border bg-background px-3 text-left read-only:bg-muted" />
              </label>
              {isDraft && <button type="submit" disabled={busy || !isDirty} className="min-h-11 rounded-full bg-foreground px-5 text-sm text-background disabled:cursor-not-allowed disabled:opacity-50">{busy ? t("sellerOnboarding.saving") : t("sellerOnboarding.save")}</button>}
            </form>
          </section>

          {application.can_submit && <section className="rounded-2xl border border-border bg-background p-5 sm:p-7">
            <h3 className="font-display text-xl">{t("sellerOnboarding.reviewTitle")}</h3>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">{t(isDirty ? "sellerOnboarding.saveBeforeSubmit" : "sellerOnboarding.reviewIntro")}</p>
            <button type="button" disabled={busy || isDirty} onClick={() => setConfirming(true)} className="mt-5 min-h-11 rounded-full bg-primary px-5 text-sm text-primary-foreground disabled:cursor-not-allowed disabled:opacity-50">{t("sellerOnboarding.submit")}</button>
            {confirming && <div className="mt-5 rounded-xl border border-primary/30 bg-primary/5 p-4" aria-labelledby="seller-submit-confirmation">
              <h4 id="seller-submit-confirmation" className="font-medium">{t("sellerOnboarding.confirmTitle")}</h4>
              <p className="mt-2 text-sm text-muted-foreground">{t("sellerOnboarding.confirmDescription")}</p>
              <div className="mt-4 flex flex-wrap gap-3">
                <button type="button" disabled={busy} onClick={() => void submitApplication()} className="min-h-11 rounded-full bg-primary px-5 text-sm text-primary-foreground disabled:opacity-50">{busy ? t("sellerOnboarding.submitting") : t("sellerOnboarding.confirmSubmit")}</button>
                <button type="button" disabled={busy} onClick={() => setConfirming(false)} className="min-h-11 rounded-full border border-border px-5 text-sm disabled:opacity-50">{t("sellerOnboarding.cancel")}</button>
              </div>
            </div>}
          </section>}
        </>
      )}
    </main>
  );
}
