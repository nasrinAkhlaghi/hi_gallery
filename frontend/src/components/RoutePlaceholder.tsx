import { Link, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "./LanguageSwitcher";

type RoutePlaceholderProps = {
  titleKey: string;
  descriptionKey?: string;
  descriptionOptions?: Record<string, string | number>;
  showLanguageSwitcher?: boolean;
};

export function RoutePlaceholder({ titleKey, descriptionKey, descriptionOptions, showLanguageSwitcher = false }: RoutePlaceholderProps) {
  const { t } = useTranslation();
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-12 text-foreground">
      <header className="flex items-center justify-between gap-4">
        <Link to="/" className="text-sm text-primary">{t("app.name")}</Link>
        {showLanguageSwitcher && <LanguageSwitcher />}
      </header>
      <p className="mt-16 text-xs uppercase tracking-[0.18em] text-muted-foreground">{t("pages.scaffoldLabel")}</p>
      <h1 className="mt-3 font-display text-3xl sm:text-4xl">{t(titleKey)}</h1>
      {descriptionKey && <p className="mt-3 text-muted-foreground">{t(descriptionKey, descriptionOptions)}</p>}
      <p className="mt-4 text-sm text-muted-foreground">{t("pages.scaffoldMessage")}</p>
    </main>
  );
}

export function BuyerRoutePlaceholder(props: Omit<RoutePlaceholderProps, "showLanguageSwitcher">) {
  return <RoutePlaceholder {...props} showLanguageSwitcher />;
}

const sellerLinks = ["", "products", "orders", "shop", "settings"];
const adminLinks = ["", "sellers", "buyers", "products", "orders", "reviews", "reports"];

export function WorkspaceLayout({ area }: { area: "Seller Studio" | "Admin Console" }) {
  const { t } = useTranslation();
  const basePath = area === "Seller Studio" ? "/seller" : "/admin";
  const links = area === "Seller Studio" ? sellerLinks : adminLinks;
  const areaLabel = area === "Seller Studio" ? t("workspace.sellerStudio") : t("workspace.adminConsole");

  return (
    <div className="min-h-screen bg-[#f8f5ef] text-foreground">
      <header className="border-b border-border px-6 py-5">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <div><Link to="/" className="text-sm text-primary">{t("app.name")}</Link><h1 className="mt-1 font-display text-xl">{areaLabel}</h1></div>
          <nav aria-label={t("workspace.navigationLabel", { area: areaLabel })} className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            {links.map((path) => {
              const label = path ? t(`pages.${path}`) : t("pages.dashboard");
              return <Link key={path || "dashboard"} to={path ? `${basePath}/${path}` : basePath} className="text-muted-foreground hover:text-foreground">{label}</Link>;
            })}
          </nav>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
