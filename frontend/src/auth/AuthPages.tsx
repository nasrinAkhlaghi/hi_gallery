import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "./AuthContext";
import { ApiError, login, registerBuyer, registerSeller } from "./api";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { AuthControls } from "./AuthControls";

function AuthFrame({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  return <main className="mx-auto min-h-screen max-w-lg px-5 py-10 text-foreground sm:px-8">
    <header className="flex flex-wrap items-center justify-between gap-3"><Link to="/" dir="ltr" className="text-sm text-primary">{t("app.name")}</Link><div className="flex flex-wrap items-center gap-3"><AuthControls /><LanguageSwitcher /><Link to="/" className="text-sm text-muted-foreground">{t("auth.backHome")}</Link></div></header>
    <section className="mt-14 rounded-2xl border border-border bg-background p-6 shadow-sm sm:p-8">{children}</section>
  </main>;
}

function errorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "EMAIL_ALREADY_REGISTERED") return "auth.emailTaken";
    if (error.code === "INVALID_CREDENTIALS") return "auth.invalidCredentials";
    if (error.code === "VALIDATION_ERROR") return "auth.validationError";
  }
  return "auth.genericError";
}

export function LoginPage() {
  const { t } = useTranslation();
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const authenticatedUser = await login(email, password);
      setUser(authenticatedUser);
      const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;
      const destination = authenticatedUser.roles.includes("SELLER")
        ? authenticatedUser.seller_status === "ACTIVE" ? "/seller" : "/seller/onboarding"
        : from || "/profile";
      navigate(destination, { replace: true });
    } catch (caught) {
      setError(errorKey(caught));
    } finally {
      setBusy(false);
    }
  }

  return <AuthFrame><h1 className="font-display text-3xl">{t("auth.loginTitle")}</h1><p className="mt-2 text-sm text-muted-foreground">{t("auth.loginIntro")}</p>
    {searchParams.get("registered") && <p role="status" className="mt-4 text-sm text-primary">{t(searchParams.get("registered") === "seller" ? "auth.sellerRegisteredLogin" : "auth.loginSuccess")}</p>}
    <form className="mt-7 space-y-5" onSubmit={submit}>
      <label className="block text-sm">{t("auth.email")}<input dir="ltr" autoComplete="email" type="email" required maxLength={255} value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-border bg-background px-3" /></label>
      <label className="block text-sm">{t("auth.password")}<input dir="ltr" autoComplete="current-password" type="password" required maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-border bg-background px-3" /></label>
      {error && <p role="alert" className="text-sm text-destructive">{t(error)}</p>}
      <button disabled={busy} className="min-h-11 w-full rounded-full bg-foreground px-5 text-sm text-background disabled:opacity-60">{busy ? t("auth.working") : t("auth.loginAction")}</button>
    </form>
    <p className="mt-6 text-sm text-muted-foreground">{t("auth.noAccount")} <Link className="text-primary underline" to="/register">{t("auth.registerLink")}</Link></p>
  </AuthFrame>;
}

export function RegistrationPage({ seller = false }: { seller?: boolean }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      if (seller) await registerSeller({ email, password, shop_name: name });
      else await registerBuyer({ email, password, display_name: name });
      navigate(seller ? "/login?registered=seller" : "/login?registered=1", { replace: true });
    } catch (caught) {
      setError(errorKey(caught));
    } finally {
      setBusy(false);
    }
  }

  return <AuthFrame><h1 className="font-display text-3xl">{t(seller ? "auth.sellerRegisterTitle" : "auth.registerTitle")}</h1><p className="mt-2 text-sm text-muted-foreground">{t("auth.registerIntro")}</p>
    <form className="mt-7 space-y-5" onSubmit={submit}>
      <label className="block text-sm">{t("auth.email")}<input dir="ltr" autoComplete="email" type="email" required maxLength={255} value={email} onChange={(event) => setEmail(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-border bg-background px-3" /></label>
      <label className="block text-sm">{t(seller ? "auth.shopName" : "auth.displayName")}<input required maxLength={150} value={name} onChange={(event) => setName(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-border bg-background px-3" /></label>
      <label className="block text-sm">{t("auth.password")}<input dir="ltr" autoComplete="new-password" type="password" required minLength={12} maxLength={128} value={password} onChange={(event) => setPassword(event.target.value)} className="mt-2 min-h-11 w-full rounded-lg border border-border bg-background px-3" /><span className="mt-1 block text-xs text-muted-foreground">{t("auth.passwordHint")}</span></label>
      {error && <p role="alert" className="text-sm text-destructive">{t(error)}</p>}
      <button disabled={busy} className="min-h-11 w-full rounded-full bg-foreground px-5 text-sm text-background disabled:opacity-60">{busy ? t("auth.working") : t(seller ? "auth.sellerRegisterAction" : "auth.registerAction")}</button>
    </form>
    <p className="mt-6 text-sm text-muted-foreground">{t("auth.haveAccount")} <Link className="text-primary underline" to="/login">{t("auth.loginLink")}</Link></p>
    <p className="mt-3 text-sm text-muted-foreground">{seller ? t("auth.buyerRegistrationPrompt") : t("auth.sellerRegistrationPrompt")} <Link className="text-primary underline" to={seller ? "/register" : "/register/seller"}>{t(seller ? "auth.buyerRegisterLink" : "auth.sellerRegisterLink")}</Link></p>
  </AuthFrame>;
}

export function RequireAuth({ children, role, activeSeller = false }: { children: ReactNode; role?: "SELLER" | "ADMIN"; activeSeller?: boolean }) {
  const { t } = useTranslation();
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <main className="grid min-h-screen place-items-center text-sm text-muted-foreground" role="status">{t("auth.loading")}</main>;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  if (role && !user.roles.includes(role)) return <Navigate to="/profile" replace />;
  if (activeSeller && user.seller_status !== "ACTIVE") return <Navigate to="/seller/onboarding" replace state={{ from: location }} />;
  return children;
}
