import { useEffect, useRef, useState } from "react";
import { ArrowDownRight, ArrowUpRight, Flower2, Heart, Menu, Search, X } from "lucide-react";
import { BrowserRouter, Link, Route, Routes, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { LanguageSwitcher } from "./components/LanguageSwitcher";
import { BuyerRoutePlaceholder, RoutePlaceholder, WorkspaceLayout } from "./components/RoutePlaceholder";

const categories = ["ceramics", "textiles", "jewelry", "homeObjects"] as const;

const buyerNavigationItems = [
  { labelKey: "navigation.discover", href: "#discover" },
  { labelKey: "navigation.categories", to: "/categories" },
  { labelKey: "navigation.cart", to: "/cart" },
  { labelKey: "navigation.orders", to: "/orders" },
  { labelKey: "navigation.profile", to: "/profile" },
  { labelKey: "navigation.ourStory", href: "#about" },
] as const;

function BuyerNavigationLinks({
  mobile = false,
  onNavigate,
}: {
  mobile?: boolean;
  onNavigate?: () => void;
}) {
  const { t } = useTranslation();
  const linkClassName = mobile
    ? "flex min-h-11 items-center rounded-lg px-3 transition hover:bg-muted hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary"
    : "transition hover:text-foreground";

  return buyerNavigationItems.map((item) => {
    if ("to" in item) {
      return (
        <Link key={item.labelKey} className={linkClassName} to={item.to} onClick={onNavigate}>
          {t(item.labelKey)}
        </Link>
      );
    }

    return (
      <a key={item.labelKey} className={linkClassName} href={item.href} onClick={onNavigate}>
        {t(item.labelKey)}
      </a>
    );
  });
}

function HomePage() {
  const { t } = useTranslation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuButtonRef = useRef<HTMLButtonElement>(null);
  const mobileNavigationRef = useRef<HTMLElement>(null);

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
    <main className="min-h-screen overflow-hidden bg-background text-foreground">
      <header className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-y-4 px-6 py-6 lg:px-12">
        <a href="#home" dir="ltr" className="flex items-center gap-2 font-display text-xl font-semibold tracking-tight" aria-label={t("app.homeLabel")}>
          <span className="grid h-9 w-9 place-items-center rounded-full bg-primary text-sm text-primary-foreground">hi</span>
          <span>gallery</span>
        </a>
        <nav className="hidden items-center gap-x-5 gap-y-2 text-sm text-muted-foreground md:order-last md:flex md:w-full md:flex-wrap md:justify-center lg:order-none lg:w-auto lg:justify-start lg:gap-x-7" aria-label={t("navigation.label")}>
          <BuyerNavigationLinks />
        </nav>
        <div className="flex items-center gap-3">
          <button className="grid h-11 w-11 place-items-center rounded-full border border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary" aria-label={t("navigation.search")}><Search size={17} /></button>
          <LanguageSwitcher className="hidden md:block" />
          <button className="hidden rounded-full bg-foreground px-5 py-3 text-sm text-background focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary sm:block">{t("actions.meetMakers")}</button>
          <button
            ref={mobileMenuButtonRef}
            type="button"
            className="grid h-11 w-11 place-items-center rounded-full border border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary md:hidden"
            aria-label={mobileMenuOpen ? t("navigation.closeMenu") : t("navigation.openMenu")}
            aria-expanded={mobileMenuOpen}
            aria-controls="mobile-buyer-navigation"
            onClick={() => setMobileMenuOpen((open) => !open)}
          >
            {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
        <nav
          ref={mobileNavigationRef}
          id="mobile-buyer-navigation"
          className={`${mobileMenuOpen ? "flex" : "hidden"} order-last w-full flex-col gap-1 rounded-2xl border border-border bg-background p-2 text-sm text-muted-foreground shadow-md md:hidden`}
          aria-label={t("navigation.label")}
        >
          <BuyerNavigationLinks mobile onNavigate={() => setMobileMenuOpen(false)} />
          <LanguageSwitcher className="w-full" onLanguageChange={() => setMobileMenuOpen(false)} />
        </nav>
      </header>

      <section id="home" className="mx-auto grid max-w-7xl items-center gap-12 px-6 pb-20 pt-10 lg:grid-cols-[1fr_0.9fr] lg:px-12 lg:pb-28 lg:pt-16">
        <div className="relative z-10">
          <p className="mb-6 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-primary"><Flower2 size={15} /> {t("home.eyebrow")}</p>
          <h1 className="max-w-xl font-display text-4xl leading-[1.07] tracking-tight sm:text-5xl md:text-6xl lg:text-7xl">{t("home.titleLineOne")}<br />{t("home.titleLineTwo")} <span className="font-serif italic text-primary">{t("home.titleHighlight")}</span><br />{t("home.titleLineThree")}</h1>
          <p className="mt-7 max-w-md text-base leading-7 text-muted-foreground">{t("home.description")}</p>
          <div className="mt-9 flex flex-wrap items-center gap-4">
            <a className="inline-flex items-center gap-3 rounded-full bg-primary px-6 py-3.5 text-sm font-medium text-primary-foreground transition hover:opacity-90" href="#discover">{t("actions.exploreGallery")} <ArrowUpRight size={16} /></a>
            <span className="text-xs text-muted-foreground">{t("home.supportingLine")}</span>
          </div>
          <div className="mt-14 flex items-center gap-4 border-t border-border pt-6 text-xs text-muted-foreground"><span className="font-serif text-2xl italic text-foreground">01</span><span>{t("home.makerStatement")}</span><ArrowDownRight size={15} className="ms-auto" /></div>
        </div>
        <div className="relative mx-auto w-full max-w-lg lg:max-w-none">
          <div className="aspect-[0.92] overflow-hidden rounded-[48%_48%_8px_8px] rtl:rounded-[48%_48%_48%_8px] bg-[#d6b896]">
            <img className="h-full w-full object-cover" src="https://images.unsplash.com/photo-1578749556568-bc2c40e68b61?auto=format&fit=crop&w=1100&q=85" alt={t("home.imageAlt")} />
          </div>
          <div className="absolute -bottom-5 start-0 rounded-2xl bg-white/95 p-4 shadow-xl shadow-stone-900/10 sm:-start-8 sm:p-5">
            <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-full bg-[#ece4d9] font-serif italic">{t("home.makerInitial")}</span><div><p className="text-sm font-medium">{t("home.imageCardTitle")}</p><p className="mt-1 text-xs text-muted-foreground">{t("home.imageCardDescription")}</p></div><Heart className="ms-3 text-primary" size={17} /></div>
          </div>
          <span className="absolute end-0 top-8 rounded-full border border-white/70 bg-background/90 px-4 py-2 text-xs tracking-wide">{t("home.imageBadge")}</span>
        </div>
      </section>

      <section id="categories" className="border-y border-border bg-[#f1ede5]">
        <div className="mx-auto max-w-7xl px-6 py-12 lg:px-12 lg:py-16">
          <div className="mb-7 flex items-end justify-between"><div><p className="text-xs uppercase tracking-[0.18em] text-primary">{t("home.categoriesEyebrow")}</p><h2 className="mt-2 font-display text-3xl tracking-tight">{t("home.categoriesTitle")}</h2></div><a href="#discover" className="hidden text-sm underline underline-offset-4 sm:block">{t("actions.viewAll")}</a></div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{categories.map((category, index) => <a key={category} href="#discover" className="group flex min-h-28 items-end justify-between rounded-2xl bg-background p-5 transition hover:-translate-y-1 hover:shadow-lg motion-reduce:transition-none motion-reduce:hover:translate-y-0"><span><span className="mb-3 block text-xs text-muted-foreground">0{index + 1}</span><span className="font-display text-lg">{t(`categories.${category}`)}</span></span><ArrowUpRight size={17} className="text-muted-foreground transition group-hover:text-primary" /></a>)}</div>
        </div>
      </section>

      <section id="discover" className="mx-auto max-w-7xl px-6 py-20 text-center lg:px-12 lg:py-28">
        <p className="text-xs uppercase tracking-[0.18em] text-primary">{t("home.discoveryEyebrow")}</p>
        <h2 className="mx-auto mt-4 max-w-2xl font-display text-3xl tracking-tight sm:text-4xl">{t("home.discoveryTitle")}</h2>
        <p className="mx-auto mt-5 max-w-lg text-sm leading-6 text-muted-foreground">{t("home.discoveryDescription")}</p>
      </section>
      <footer id="about" className="border-t border-border px-6 py-7 text-center text-xs text-muted-foreground">{t("app.name")} <span className="mx-2">·</span> {t("home.footerTagline")}</footer>
    </main>
  );
}

function ProductPlaceholder() {
  const { id } = useParams();
  return <BuyerRoutePlaceholder titleKey="pages.productDetails" descriptionKey="pages.productDescription" descriptionOptions={{ id: `\u2068${id ?? ""}\u2069` }} />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/browse" element={<BuyerRoutePlaceholder titleKey="pages.browse" />} />
        <Route path="/products/:id" element={<ProductPlaceholder />} />
        <Route path="/categories" element={<BuyerRoutePlaceholder titleKey="pages.categories" />} />
        <Route path="/cart" element={<BuyerRoutePlaceholder titleKey="pages.cart" />} />
        <Route path="/checkout" element={<BuyerRoutePlaceholder titleKey="pages.checkout" />} />
        <Route path="/orders" element={<BuyerRoutePlaceholder titleKey="pages.orders" />} />
        <Route path="/reviews" element={<BuyerRoutePlaceholder titleKey="pages.reviews" />} />
        <Route path="/profile" element={<BuyerRoutePlaceholder titleKey="pages.profile" />} />
        <Route path="/seller" element={<WorkspaceLayout area="seller" />}>
          <Route index element={<RoutePlaceholder titleKey="pages.dashboard" />} />
          <Route path="products" element={<RoutePlaceholder titleKey="pages.products" />} />
          <Route path="orders" element={<RoutePlaceholder titleKey="pages.orders" />} />
          <Route path="shop" element={<RoutePlaceholder titleKey="pages.shop" />} />
          <Route path="settings" element={<RoutePlaceholder titleKey="pages.settings" />} />
        </Route>
        <Route path="/admin" element={<WorkspaceLayout area="admin" />}>
          <Route index element={<RoutePlaceholder titleKey="pages.dashboard" />} />
          <Route path="sellers" element={<RoutePlaceholder titleKey="pages.sellers" />} />
          <Route path="buyers" element={<RoutePlaceholder titleKey="pages.buyers" />} />
          <Route path="products" element={<RoutePlaceholder titleKey="pages.products" />} />
          <Route path="orders" element={<RoutePlaceholder titleKey="pages.orders" />} />
          <Route path="reviews" element={<RoutePlaceholder titleKey="pages.reviews" />} />
          <Route path="reports" element={<RoutePlaceholder titleKey="pages.reports" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
