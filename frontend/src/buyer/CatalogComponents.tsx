import { useState, type ReactNode } from "react";
import { Flower2, ArrowUpRight } from "lucide-react";
import { Link, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AuthControls } from "../auth/AuthControls";
import { ApiError } from "../auth/api";
import { LanguageSwitcher } from "../components/LanguageSwitcher";
import { productImageUrl } from "../seller/productsApi";
import { categoryLink, getCategories, type PublicProduct, type Page, type Category } from "./catalogApi";
import { usePublicData } from "./usePublicData";

export const catalogButton = "inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-current/25 px-5 py-2.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-40";
export const catalogInput = "min-h-11 min-w-0 w-full rounded-xl border border-current/25 bg-transparent px-3 py-2 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2";

export function BuyerLayout() {
  const { t } = useTranslation();
  return <div className="min-h-screen bg-background text-foreground">
    <a href="#catalog-content" className="sr-only focus:not-sr-only focus:block focus:p-3">{t("catalog.skip")}</a>
    <header className="border-b border-border"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-5 sm:px-8">
      <Link to="/" dir="ltr" className="flex items-center gap-2 font-display text-xl"><span className="grid h-9 w-9 place-items-center rounded-full bg-primary text-sm text-primary-foreground">hi</span>gallery</Link>
      <nav aria-label={t("navigation.label")} className="order-last flex w-full flex-wrap gap-x-5 gap-y-1 text-sm sm:order-none sm:w-auto">
        {[["/browse", "pages.browse"], ["/categories", "pages.categories"], ["/cart", "pages.cart"], ["/orders", "pages.orders"], ["/profile", "pages.profile"]].map(([to, label]) => <Link key={to} className="inline-flex min-h-11 items-center hover:underline focus-visible:outline focus-visible:outline-2" to={to}>{t(label)}</Link>)}
      </nav>
      <div className="flex flex-wrap items-center gap-3"><LanguageSwitcher /><AuthControls /></div>
    </div></header>
    <main id="catalog-content" tabIndex={-1}><Outlet /></main>
    <footer className="border-t border-border px-5 py-8 text-center text-xs text-muted-foreground">{t("home.footerTagline")}</footer>
  </div>;
}

export function CatalogImage({ src, alt, className = "", eager = false, fit = "cover" }: { src?: string | null; alt: string; className?: string; eager?: boolean; fit?: "cover" | "contain" }) {
  const { t } = useTranslation();
  const [failed, setFailed] = useState("");
  let url = "";
  try {
    if (src) { const resolved = productImageUrl(src); if (["http:", "https:"].includes(new URL(resolved).protocol)) url = resolved; }
  } catch { /* Missing/invalid media uses the same fallback as a failed image. */ }
  return url && failed !== url ? <img src={url} alt={alt} loading={eager ? "eager" : "lazy"} referrerPolicy="no-referrer" onError={() => setFailed(url)} className={`h-full w-full ${fit === "contain" ? "object-contain" : "object-cover"} ${className}`} />
    : <div role="img" aria-label={t("catalog.noImage", { name: alt })} className={`grid h-full w-full place-items-center bg-current/5 ${className}`}><Flower2 aria-hidden="true" size={36} className="opacity-40" /></div>;
}

export function CatalogError({ error, retry, kind = "products" }: { error: unknown; retry: () => void; kind?: "shop" | "product" | "products" | "categories" }) {
  const { t } = useTranslation();
  const status = error instanceof ApiError ? error.status : 0;
  const key = status === 404 ? (kind === "shop" ? "shopNotFound" : "productNotFound") : status === 422 ? "invalidFilters" : "loadError";
  return <div role="alert" className="space-y-4 rounded-2xl border border-current/25 p-6">
    <p className="text-sm leading-7">{t(`catalog.${key}`)}</p>
    <div className="flex flex-wrap gap-3">{status !== 404 && <button type="button" className={catalogButton} onClick={retry}>{t("catalog.retry")}</button>}<Link className={catalogButton} to="/browse">{t("catalog.backToBrowse")}</Link></div>
  </div>;
}

export function ProductCard({ product }: { product: PublicProduct }) {
  const { t } = useTranslation();
  const unavailable = product.status === "SOLD_OUT" || product.stock === 0;
  return <article className="min-w-0 overflow-hidden rounded-2xl border border-current/20" style={{ backgroundColor: "var(--shop-surface, hsl(var(--background)))" }}>
    <Link to={`/products/${encodeURIComponent(product.id)}`} className="group block focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-[-3px]">
      <div className="aspect-[4/5] overflow-hidden"><CatalogImage src={product.images[0]?.url} alt={product.name} className="transition duration-300 group-hover:scale-[1.03] motion-reduce:transform-none motion-reduce:transition-none" /></div>
      <div className="space-y-3 px-5 pt-5"><h2 className="break-words font-display text-xl [overflow-wrap:anywhere]">{product.name}</h2>
        <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium"><bdi dir="ltr">{product.price}</bdi></p>{unavailable && <span className="rounded-full border border-current/25 px-3 py-1 text-xs">{t("catalog.soldOut")}</span>}</div>
      </div>
    </Link>
    <div className="space-y-2 p-5 pt-3 text-sm"><Link className="block break-words underline decoration-current/30 underline-offset-4 hover:decoration-current" to={`/shops/${encodeURIComponent(product.seller.id)}`}>{product.seller.shop_name}</Link>
      <Link className="inline-block text-xs opacity-75 hover:underline" to={categoryLink(product.category.id)}>{product.category.name}</Link>
    </div>
  </article>;
}

export function ProductResults({ data, loading, error, retry, page, onPage, emptyShop = false, shopResults = false }: {
  data: Page<PublicProduct> | null; loading: boolean; error: unknown; retry: () => void; page: number; onPage: (page: number) => void; emptyShop?: boolean; shopResults?: boolean;
}) {
  const { t } = useTranslation();
  if (loading) return <p role="status" className="py-8 text-sm">{t("catalog.loadingProducts")}</p>;
  if (error) return <CatalogError error={error} retry={retry} kind={shopResults ? "shop" : "products"} />;
  if (!data) return null;
  return <div className="space-y-7">
    <p role="status" className="text-sm">{t("catalog.results", { count: data.total })}</p>
    {data.items.length ? <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{data.items.map((product) => <ProductCard key={product.id} product={product} />)}</div>
      : <div className="space-y-4 rounded-2xl border border-current/20 p-8 text-center"><Flower2 aria-hidden="true" className="mx-auto opacity-60" size={30} /><p className="text-sm leading-7">{t(page > 0 ? "catalog.emptyPage" : emptyShop ? "catalog.emptyShop" : "catalog.emptyProducts")}</p>{page > 0 && <button type="button" className={catalogButton} onClick={() => onPage(0)}>{t("catalog.firstPage")}</button>}</div>}
    {data.total > 0 && <nav aria-label={t("catalog.pagination")} className="flex flex-wrap items-center justify-center gap-3">
      <button type="button" className={catalogButton} disabled={page === 0} onClick={() => onPage(page - 1)}>{t("catalog.previous")}</button>
      <span className="text-sm">{t("catalog.page", { current: page + 1, total: Math.ceil(data.total / data.page_size) })}</span>
      <button type="button" className={catalogButton} disabled={(page + 1) * data.page_size >= data.total} onClick={() => onPage(page + 1)}>{t("catalog.next")}</button>
    </nav>}
  </div>;
}

export function CategorySelect({ value, onChange, categories }: { value: string; onChange: (value: string) => void; categories: Category[] }) {
  const { t } = useTranslation();
  return <label className="block min-w-0 space-y-2 text-sm"><span>{t("catalog.category")}</span><select className={catalogInput} value={value} onChange={(e) => onChange(e.target.value)}>
    <option value="">{t("catalog.allCategories")}</option>
    {value && !categories.some((item) => item.id === value) && <option value={value}>{t("catalog.selectedCategory")}</option>}
    {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
  </select></label>;
}

export function CategoryTiles({ limit }: { limit?: number }) {
  const { t } = useTranslation();
  const { data, loading, error, retry } = usePublicData<Category[]>("/categories", getCategories);
  if (loading) return <p role="status">{t("catalog.loadingCategories")}</p>;
  if (error) return <CatalogError error={error} retry={retry} kind="categories" />;
  if (!data?.length) return <p className="text-sm leading-7 text-muted-foreground">{t("catalog.emptyCategories")}</p>;
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">{data.slice(0, limit).map((category, index) => <Link key={category.id} to={categoryLink(category.id)} className="group flex min-h-36 min-w-0 items-end justify-between gap-3 rounded-2xl border border-border bg-background p-6 transition hover:border-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary">
    <span className="min-w-0"><span className="mb-5 block text-xs text-muted-foreground">{String(index + 1).padStart(2, "0")}</span><span className="break-words font-display text-xl">{category.name}</span></span><ArrowUpRight aria-hidden="true" className="shrink-0 text-primary rtl:-scale-x-100" size={18} />
  </Link>)}</div>;
}

export function CatalogPage({ children }: { children: ReactNode }) {
  return <div className="mx-auto max-w-7xl space-y-8 px-5 py-10 sm:px-8 sm:py-14">{children}</div>;
}
