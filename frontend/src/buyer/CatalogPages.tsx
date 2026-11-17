import { useEffect, useState, type CSSProperties, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Search } from "lucide-react";
import { shopThemes } from "../shop/themes";
import { categoryLink, getCategories, productListPath, type Category, type Page, type PublicProduct, type PublicShop } from "./catalogApi";
import { usePublicData } from "./usePublicData";
import { CatalogError, CatalogImage, CatalogPage, CategorySelect, CategoryTiles, ProductResults, catalogButton, catalogInput } from "./CatalogComponents";

function readPage(params: URLSearchParams) {
  const value = Number(params.get("page") ?? "0");
  return Number.isSafeInteger(value) && value >= 0 ? value : -1;
}

export function BrowsePage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const category = params.get("category_id") ?? "";
  const page = readPage(params);
  const [search, setSearch] = useState(q);
  useEffect(() => setSearch(q), [q]);
  const products = usePublicData<Page<PublicProduct>>(productListPath(page, category, q));
  const categories = usePublicData<Category[]>("/categories", getCategories);

  function filter(nextCategory: string, nextSearch: string) {
    const next = new URLSearchParams();
    if (nextSearch.trim()) next.set("q", nextSearch.trim());
    if (nextCategory) next.set("category_id", nextCategory);
    setParams(next);
  }
  function submit(event: FormEvent) { event.preventDefault(); filter(category, search); }
  function onPage(nextPage: number) { const next = new URLSearchParams(params); next.set("page", String(nextPage)); setParams(next); }

  return <CatalogPage>
    <header className="max-w-2xl space-y-3"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">{t("catalog.eyebrow")}</p><h1 className="font-display text-4xl sm:text-5xl">{t("pages.browse")}</h1><p className="text-sm leading-7 text-muted-foreground">{t("catalog.browseIntro")}</p></header>
    <form onSubmit={submit} aria-label={t("catalog.searchForm")} className="grid items-end gap-4 rounded-2xl border border-border p-5 sm:grid-cols-[minmax(0,1fr)_minmax(0,0.6fr)_auto]">
      <label className="block min-w-0 space-y-2 text-sm"><span>{t("catalog.search")}</span><input type="search" maxLength={200} value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t("catalog.searchPlaceholder")} className={catalogInput} /></label>
      <CategorySelect value={category} onChange={(value) => filter(value, search)} categories={categories.data ?? []} />
      <button type="submit" className={`${catalogButton} bg-primary text-primary-foreground`}><Search aria-hidden="true" size={16} />{t("catalog.searchAction")}</button>
      {(q || category) && <Link to="/browse" className="text-sm underline underline-offset-4">{t("catalog.clearFilters")}</Link>}
    </form>
    {!!categories.error && <CatalogError error={categories.error} retry={categories.retry} kind="categories" />}
    <ProductResults {...products} page={page} onPage={onPage} />
  </CatalogPage>;
}

export function CategoriesPage() {
  const { t } = useTranslation();
  return <CatalogPage><header className="max-w-2xl space-y-3"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">{t("catalog.eyebrow")}</p><h1 className="font-display text-4xl sm:text-5xl">{t("pages.categories")}</h1><p className="text-sm leading-7 text-muted-foreground">{t("catalog.categoriesIntro")}</p></header><CategoryTiles /></CatalogPage>;
}

export function PublicShopPage() {
  const { t } = useTranslation();
  const { sellerId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const category = params.get("category_id") ?? "";
  const page = readPage(params);
  const shop = usePublicData<PublicShop>(`/shops/${encodeURIComponent(sellerId)}`);
  const products = usePublicData<Page<PublicProduct>>(productListPath(page, category, "", sellerId));
  const categories = usePublicData<Category[]>("/categories", getCategories);
  const palette = shopThemes[shop.data?.theme_id ?? "gallery"];
  const style = { backgroundColor: palette.background, color: palette.text, "--shop-surface": palette.surface } as CSSProperties;
  function onPage(value: number) { const next = new URLSearchParams(params); next.set("page", String(value)); setParams(next); }
  function filter(value: string) { const next = new URLSearchParams(); if (value) next.set("category_id", value); setParams(next); }

  if (shop.loading) return <CatalogPage><p role="status">{t("catalog.loadingShop")}</p></CatalogPage>;
  if (shop.error) return <CatalogPage><h1 className="font-display text-3xl">{t("pages.shop")}</h1><CatalogError error={shop.error} retry={shop.retry} kind="shop" /></CatalogPage>;
  if (!shop.data) return null;
  return <div style={style} data-shop-theme={shop.data.theme_id}>
    <CatalogPage>
      <Link to="/browse" className="inline-flex min-h-11 items-center text-sm underline underline-offset-4">{t("catalog.backToBrowse")}</Link>
      <header className="grid items-center gap-6 border-b border-current/20 pb-9 sm:grid-cols-[auto_minmax(0,1fr)]">
        <div className="h-24 w-24 overflow-hidden rounded-3xl border border-current/20" style={{ backgroundColor: palette.surface }}><CatalogImage src={shop.data.logo_url} alt={t("catalog.shopLogo", { name: shop.data.shop_name })} eager /></div>
        <div className="max-w-2xl space-y-3"><p className="text-xs font-semibold uppercase tracking-[0.16em]" style={{ color: palette.accent }}>{t("sellerShop.handmade")}</p>
          <h1 className="break-words font-display text-4xl [overflow-wrap:anywhere] sm:text-5xl">{shop.data.shop_name}</h1>
          {shop.data.category && <p className="text-sm" style={{ color: palette.accent }}>{shop.data.category.name}</p>}
          {shop.data.description && <p className="whitespace-pre-wrap break-words text-sm leading-7 [overflow-wrap:anywhere]" style={{ color: palette.muted }}>{shop.data.description}</p>}
        </div>
      </header>
      <section aria-labelledby="shop-products-title" className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-5"><h2 id="shop-products-title" className="font-display text-2xl">{t("catalog.shopProducts")}</h2><div className="w-full sm:w-64"><CategorySelect value={category} onChange={filter} categories={categories.data ?? []} /></div></div>
        {!!categories.error && <CatalogError error={categories.error} retry={categories.retry} kind="categories" />}
        <ProductResults {...products} page={page} onPage={onPage} emptyShop={!category} shopResults />
      </section>
    </CatalogPage>
  </div>;
}

export function ProductDetailPage() {
  const { t } = useTranslation();
  const { id = "" } = useParams();
  const product = usePublicData<PublicProduct>(`/products/${encodeURIComponent(id)}`);
  const [selectedId, setSelectedId] = useState("");
  const data = product.data;
  const selected = data?.images.find((image) => image.id === selectedId) ?? data?.images[0];
  if (product.loading) return <CatalogPage><p role="status">{t("catalog.loadingProduct")}</p></CatalogPage>;
  if (product.error) return <CatalogPage><h1 className="font-display text-3xl">{t("pages.productDetails")}</h1><CatalogError error={product.error} retry={product.retry} kind="product" /></CatalogPage>;
  if (!data) return null;
  const unavailable = data.status === "SOLD_OUT" || data.stock === 0;
  return <CatalogPage>
    <nav aria-label={t("catalog.breadcrumb")} className="flex flex-wrap items-center gap-3 text-sm"><Link className="underline underline-offset-4" to="/browse">{t("pages.browse")}</Link><span aria-hidden="true">/</span><Link className="underline underline-offset-4" to={categoryLink(data.category.id)}>{data.category.name}</Link></nav>
    <div className="grid items-start gap-9 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <section aria-label={t("catalog.gallery")} className="min-w-0 space-y-4">
        <div className="aspect-square overflow-hidden rounded-3xl border border-border"><CatalogImage src={selected?.url} alt={data.name} fit="contain" eager /></div>
        {data.images.length > 1 && <div className="flex flex-wrap gap-3">{data.images.map((image, index) => <button key={image.id} type="button" aria-label={t("catalog.selectImage", { number: index + 1, name: data.name })} aria-pressed={selected?.id === image.id} onClick={() => setSelectedId(image.id)} className="h-20 w-20 overflow-hidden rounded-xl border border-border focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary aria-pressed:border-primary aria-pressed:ring-2 aria-pressed:ring-primary">
          <CatalogImage src={image.url} alt={t("catalog.imageAlt", { number: index + 1, name: data.name })} />
        </button>)}</div>}
      </section>
      <section className="min-w-0 space-y-6 lg:sticky lg:top-6">
        <Link className="inline-flex min-h-11 items-center text-sm font-medium text-primary underline underline-offset-4" to={`/shops/${encodeURIComponent(data.seller.id)}`}>{data.seller.shop_name}</Link>
        <h1 className="break-words font-display text-4xl leading-tight [overflow-wrap:anywhere] sm:text-5xl">{data.name}</h1>
        <p className="text-2xl font-medium"><span className="sr-only">{t("catalog.price")}: </span><bdi dir="ltr">{data.price}</bdi></p>
        <p role="status" className="inline-flex rounded-full border border-border px-4 py-2 text-sm">{t(unavailable ? "catalog.soldOut" : "catalog.inStock", { count: data.stock })}</p>
        <div className="space-y-3 border-t border-border pt-6"><h2 className="font-display text-xl">{t("catalog.aboutPiece")}</h2><p className="whitespace-pre-wrap break-words text-sm leading-8 text-muted-foreground [overflow-wrap:anywhere]">{data.description || t("catalog.noDescription")}</p></div>
        <p className="rounded-2xl bg-muted p-5 text-sm leading-7 text-muted-foreground">{t("catalog.purchaseNotice")}</p>
        <Link className={catalogButton} to={`/shops/${encodeURIComponent(data.seller.id)}`}>{t("catalog.visitShop")}</Link>
      </section>
    </div>
  </CatalogPage>;
}
