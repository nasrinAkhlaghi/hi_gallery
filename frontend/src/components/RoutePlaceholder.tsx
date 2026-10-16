import { useEffect, useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "./LanguageSwitcher";
import { AuthControls } from "../auth/AuthControls";

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
      <header className="flex flex-wrap items-center justify-between gap-4">
        <Link to="/" className="text-sm text-primary">{t("app.name")}</Link>
        <AuthControls />
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

type WorkspaceArea = "seller" | "admin";

const sellerLinks = ["dashboard", "products", "orders", "shop", "settings"] as const;
const adminLinks = ["dashboard", "sellers", "buyers", "products", "orders", "reviews", "reports"] as const;

function WorkspaceNavigationLinks({
  area,
  mobile = false,
  onNavigate,
}: {
  area: WorkspaceArea;
  mobile?: boolean;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation();
  const basePath = `/${area}`;
  const links = area === "seller" ? sellerLinks : adminLinks;

  return links.map((page) => {
    const to = page === "dashboard" ? basePath : `${basePath}/${page}`;

    return (
      <NavLink
        key={page}
        to={to}
        end={page === "dashboard"}
        onClick={onNavigate}
        className={({ isActive }) =>
          `${mobile ? "flex min-h-11 items-center rounded-lg px-3" : "py-2"} transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${
            isActive
              ? "font-medium text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`
        }
      >
        {t(`workspace.navigation.${page}`)}
      </NavLink>
    );
  });
}

export function WorkspaceLayout({ area }: { area: WorkspaceArea }) {
  const { t } = useTranslation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileNavigationRef = useRef<HTMLElement>(null);
  const areaLabel = t(area === "seller" ? "workspace.sellerStudio" : "workspace.adminConsole");

  useEffect(() => {
    if (!mobileMenuOpen) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setMobileMenuOpen(false);
        mobileMenuButtonRef.current?.focus();
      }
    }

    function handlePointerDown(event: PointerEvent) {
      if (!(event.target instanceof Node)) return;
      if (
        !mobileNavigationRef.current?.contains(event.target) &&
        !mobileMenuButtonRef.current?.contains(event.target)
      ) {
        setMobileMenuOpen(false);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    document.addEventListener("pointerdown", handlePointerDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.removeEventListener("pointerdown", handlePointerDown);
    };
  }, [mobileMenuOpen]);

  return (
    <div className="min-h-screen bg-[#f8f5ef] text-foreground">
      <header className="border-b border-border px-6 py-5">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <div>
            <Link to="/" dir="ltr" className="text-sm text-primary">{t("app.name")}</Link>
            <h1 className="mt-1 font-display text-xl">{areaLabel}</h1>
          </div>
          <nav aria-label={t("workspace.navigationLabel", { area: areaLabel })} className="hidden items-center gap-x-5 text-sm md:flex">
            <WorkspaceNavigationLinks area={area} />
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden sm:block"><AuthControls /></span>
            <LanguageSwitcher className="hidden md:block" />
            <button
              ref={mobileMenuButtonRef}
              type="button"
              className="grid h-11 w-11 place-items-center rounded-full border border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary md:hidden"
              aria-label={t(mobileMenuOpen ? "workspace.closeMenu" : "workspace.openMenu", { area: areaLabel })}
              aria-expanded={mobileMenuOpen}
              aria-controls={`${area}-mobile-navigation`}
              onClick={() => setMobileMenuOpen((open) => !open)}
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
          <nav
            ref={mobileNavigationRef}
            id={`${area}-mobile-navigation`}
            aria-label={t("workspace.navigationLabel", { area: areaLabel })}
            className={`${mobileMenuOpen ? "flex" : "hidden"} order-last w-full flex-col gap-1 rounded-2xl border border-border bg-background p-2 text-sm shadow-md md:hidden`}
          >
            <WorkspaceNavigationLinks area={area} mobile onNavigate={() => setMobileMenuOpen(false)} />
            <LanguageSwitcher className="mt-1 w-full" onLanguageChange={() => setMobileMenuOpen(false)} />
            <div className="px-3 py-2"><AuthControls /></div>
          </nav>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
