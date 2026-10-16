import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "./AuthContext";

export function AuthControls() {
  const { t } = useTranslation();
  const { user, loading, logout } = useAuth();
  if (loading) return null;
  if (!user) return <Link to="/login" className="rounded-full border border-border px-4 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">{t("auth.loginAction")}</Link>;
  return <div className="flex items-center gap-3 text-sm"><Link to="/profile" dir="ltr" className="max-w-[35vw] truncate text-muted-foreground hover:text-foreground">{user.email}</Link><button type="button" onClick={() => void logout()} className="min-h-10 rounded-full border border-border px-4 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">{t("auth.logout")}</button></div>;
}
