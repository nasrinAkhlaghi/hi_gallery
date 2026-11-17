import { useEffect, useState, type FormEvent } from "react";
import { Check, Flower2, ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError } from "../auth/api";
import { shopThemeIds, shopThemes, type ShopThemeId } from "../shop/themes";
import { getCategories, type Category } from "./productsApi";
import { getShop, saveShop, type ShopSettings } from "./shopApi";

type FormFields = { shop_name: string; description: string; logo_url: string; shop_category_id: string; theme_id: ShopThemeId };
const inputClass = "mt-2 min-h-11 w-full rounded-xl border border-border bg-background px-3 py-2.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary";
const buttonClass = "inline-flex min-h-11 items-center justify-center gap-2 rounded-full border border-border px-5 py-2.5 text-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary disabled:cursor-not-allowed disabled:opacity-50";

function fieldsFrom(shop: ShopSettings): FormFields {
  return { shop_name: shop.shop_name, description: shop.description ?? "", logo_url: shop.logo_url ?? "",
    shop_category_id: shop.shop_category_id ?? "", theme_id: shop.theme_id };
}

function errorKey(error: unknown) {
  if (error instanceof ApiError) {
    if (error.code === "CATEGORY_UNAVAILABLE") return "categoryUnavailable";
    if (error.code === "INVALID_SHOP_THEME") return "invalidTheme";
    if (error.status === 403) return "forbidden";
    if (error.status === 422) return "validationError";
  }
  return "requestError";
}

function validLogo(value: string): boolean {
  if (!value.trim()) return true;
  try {
    const url = new URL(value.trim());
    return ["http:", "https:"].includes(url.protocol) && !!url.hostname && !url.username && !url.password;
  } catch { return false; }
}

function ShopPreview({ fields, category }: { fields: FormFields; category: string }) {
  const { t } = useTranslation();
  const [failedLogo, setFailedLogo] = useState("");
  const palette = shopThemes[fields.theme_id];
  const logo = validLogo(fields.logo_url) ? fields.logo_url.trim() : "";
  return <section aria-label={t("sellerShop.preview")} className="overflow-hidden rounded-3xl border" style={{ backgroundColor: palette.background, color: palette.text, borderColor: palette.border }}>
    <div className="flex items-center justify-between border-b px-5 py-4 text-xs" style={{ borderColor: palette.border, color: palette.muted }}>
      <span dir="ltr" className="font-semibold">hi gallery</span><span>{t(`sellerShop.themes.${fields.theme_id}.name`)}</span>
    </div>
    <div className="space-y-5 px-6 py-9 sm:px-8">
      <div className="grid h-16 w-16 place-items-center overflow-hidden rounded-2xl border" style={{ backgroundColor: palette.surface, borderColor: palette.border }}>
        {logo && logo !== failedLogo ? <img src={logo} referrerPolicy="no-referrer" alt={t("sellerShop.logoAlt", { shop: fields.shop_name })} className="h-full w-full object-cover" onError={() => setFailedLogo(logo)} /> : <Flower2 aria-hidden="true" size={30} style={{ color: palette.accent }} />}
      </div>
      <div className="space-y-3">
        <p className="text-xs font-medium uppercase tracking-[0.15em]" style={{ color: palette.accent }}>{t("sellerShop.handmade")}</p>
        <h3 className="break-words font-display text-3xl leading-tight [overflow-wrap:anywhere]">{fields.shop_name.trim() || t("sellerShop.previewName")}</h3>
        {category && <p className="break-words text-xs font-medium" style={{ color: palette.accent }}>{category}</p>}
        <p className="whitespace-pre-wrap break-words text-sm leading-7 [overflow-wrap:anywhere]" style={{ color: palette.muted }}>{fields.description.trim() || t("sellerShop.previewDescription")}</p>
      </div>
      <div className="border-t pt-5" style={{ borderColor: palette.border }}>
        <p className="text-sm font-medium">{t("sellerShop.previewProducts")}</p>
        <div aria-hidden="true" className="mt-4 grid grid-cols-3 gap-3">{[0, 1, 2].map((index) => <div key={index} className="rounded-xl border p-2" style={{ backgroundColor: palette.surface, borderColor: palette.border }}>
          <div className="grid aspect-square place-items-center rounded-lg" style={{ backgroundColor: palette.background }}><Flower2 size={24} style={{ color: palette.accent }} /></div>
          <div className="mt-3 h-1.5 w-3/4 rounded-full opacity-30" style={{ backgroundColor: palette.muted }} /><div className="mb-1 mt-2 h-1.5 w-1/2 rounded-full opacity-20" style={{ backgroundColor: palette.muted }} />
        </div>)}</div>
        <p className="mt-4 text-xs leading-6" style={{ color: palette.muted }}>{t("sellerShop.previewProductsHint")}</p>
      </div>
    </div>
  </section>;
}

export function SellerShopPage() {
  const { t } = useTranslation();
  const [shop, setShop] = useState<ShopSettings | null>(null);
  const [fields, setFields] = useState<FormFields | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [forbidden, setForbidden] = useState(false);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true); setError(""); setSaved(false); setForbidden(false);
    Promise.all([getShop(), getCategories()]).then(([result, options]) => {
      if (!active) return;
      setShop(result); setFields(fieldsFrom(result)); setCategories(options);
    }).catch((reason) => {
      if (active) { setError(errorKey(reason)); setForbidden(reason instanceof ApiError && reason.status === 403); }
    }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [reload]);

  const dirty = fields !== null && shop !== null && JSON.stringify(fields) !== JSON.stringify(fieldsFrom(shop));
  const existingDisabledCategory = !!fields?.shop_category_id && !categories.some((category) => category.id === fields.shop_category_id);
  const categoryName = categories.find((category) => category.id === fields?.shop_category_id)?.name ?? "";

  function change<K extends keyof FormFields>(key: K, value: FormFields[K]) {
    setFields((current) => current ? { ...current, [key]: value } : current);
    setSaved(false); setError("");
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!fields || !dirty || busy || forbidden) return;
    setError(""); setSaved(false);
    if (!fields.shop_name.trim() || fields.shop_name.length > 150 || fields.description.length > 10000 || fields.logo_url.length > 2048 || !validLogo(fields.logo_url)) {
      setError("validationError"); return;
    }
    setBusy(true);
    try {
      const result = await saveShop({ ...fields, shop_name: fields.shop_name.trim(), description: fields.description.trim() || null,
        logo_url: fields.logo_url.trim() || null, shop_category_id: fields.shop_category_id || null });
      setShop(result); setFields(fieldsFrom(result)); setSaved(true);
    } catch (reason) {
      setError(errorKey(reason));
      if (reason instanceof ApiError && reason.status === 403) setForbidden(true);
    } finally { setBusy(false); }
  }

  return <main className="mx-auto max-w-6xl space-y-8 px-5 py-9 sm:px-8 sm:py-12">
    <header className="flex flex-wrap items-start justify-between gap-5">
      <div className="max-w-xl"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">{t("sellerShop.eyebrow")}</p>
        <h2 className="mt-3 font-display text-3xl sm:text-4xl">{t("sellerShop.title")}</h2><p className="mt-3 text-sm leading-7 text-muted-foreground">{t("sellerShop.intro")}</p></div>
      {shop && <Link className={buttonClass} to={`/shops/${encodeURIComponent(shop.id)}`}>{t("sellerShop.viewShop")}<ArrowUpRight aria-hidden="true" className="rtl:-scale-x-100" size={16} /></Link>}
    </header>
    {loading && <p role="status">{t("sellerShop.loading")}</p>}
    {error && <div role="alert" className="space-y-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <p>{t(`sellerShop.${error}`)}</p>
      {forbidden ? <Link className="underline underline-offset-4" to="/seller/onboarding">{t("sellerShop.viewStatus")}</Link> : !fields && <button type="button" className={buttonClass} onClick={() => setReload((value) => value + 1)}>{t("sellerShop.retry")}</button>}
    </div>}
    {saved && <p role="status" className="rounded-xl border border-primary/30 bg-primary/5 px-4 py-3 text-sm">{t("sellerShop.saved")}</p>}
    {!loading && shop && fields && <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
      <form onSubmit={submit} aria-label={t("sellerShop.formLabel")} className="min-w-0 space-y-6">
        <fieldset disabled={busy || forbidden} className="min-w-0 space-y-6 disabled:opacity-70">
          <section className="space-y-5 rounded-2xl border border-border bg-background p-5 sm:p-7">
            <h3 className="font-display text-xl">{t("sellerShop.details")}</h3>
            <label className="block text-sm font-medium">{t("sellerShop.shopName")}<input required maxLength={150} autoComplete="organization" className={inputClass} value={fields.shop_name} onChange={(e) => change("shop_name", e.target.value)} /></label>
            <label className="block text-sm font-medium">{t("sellerShop.description")}<textarea rows={4} maxLength={10000} className={inputClass} value={fields.description} onChange={(e) => change("description", e.target.value)} /></label>
            <label className="block text-sm font-medium">{t("sellerShop.logoUrl")}<input type="url" dir="ltr" maxLength={2048} className={`${inputClass} text-left`} value={fields.logo_url} onChange={(e) => change("logo_url", e.target.value)} /></label>
            <label className="block text-sm font-medium">{t("sellerShop.category")}<select aria-describedby="shop-category-help" className={inputClass} value={fields.shop_category_id} onChange={(e) => change("shop_category_id", e.target.value)}>
              <option value="">{t("sellerShop.noCategory")}</option>
              {existingDisabledCategory && <option value={fields.shop_category_id}>{t("sellerShop.existingCategory")}</option>}
              {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
            </select></label>
            <p id="shop-category-help" className="text-xs leading-6 text-muted-foreground">{t("sellerShop.categoryHint")}</p>
            {categories.length === 0 && <p className="text-sm text-muted-foreground">{t("sellerShop.noCategories")}</p>}
          </section>
          <fieldset className="min-w-0 rounded-2xl border border-border bg-background p-5 sm:p-7">
            <legend className="px-2 font-display text-xl">{t("sellerShop.theme")}</legend>
            <p className="mb-5 text-sm leading-6 text-muted-foreground">{t("sellerShop.themeHint")}</p>
            <div className="grid gap-3 sm:grid-cols-3">{shopThemeIds.map((id) => {
              const palette = shopThemes[id];
              return <label key={id} className="relative block cursor-pointer">
                <input type="radio" name="shop-theme" className="peer sr-only" value={id} checked={fields.theme_id === id} onChange={() => change("theme_id", id)} aria-label={t(`sellerShop.themes.${id}.name`)} />
                <span className="block h-full rounded-xl border border-border p-3 peer-checked:border-primary peer-checked:ring-1 peer-checked:ring-primary peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-4 peer-focus-visible:outline-primary">
                  <span aria-hidden="true" className="mb-3 flex h-16 items-end gap-1.5 rounded-lg p-2" style={{ backgroundColor: palette.background }}>
                    <span className="h-8 flex-1 rounded" style={{ backgroundColor: palette.surface, border: `1px solid ${palette.border}` }} /><span className="h-10 flex-1 rounded" style={{ backgroundColor: palette.accent }} /><span className="h-6 flex-1 rounded" style={{ backgroundColor: palette.border }} />
                  </span>
                  <span className="flex items-center justify-between gap-2 text-sm font-medium">{t(`sellerShop.themes.${id}.name`)}{fields.theme_id === id && <Check size={16} aria-hidden="true" className="shrink-0 text-primary" />}</span>
                  <span className="mt-1 block text-xs leading-5 text-muted-foreground">{t(`sellerShop.themes.${id}.description`)}</span>
                </span>
              </label>;
            })}</div>
          </fieldset>
          <div className="flex flex-wrap items-center gap-3">
            <button type="submit" disabled={!dirty} className={`${buttonClass} bg-primary text-primary-foreground`}>{t(busy ? "sellerShop.saving" : "sellerShop.save")}</button>
            <button type="button" disabled={!dirty} className={buttonClass} onClick={() => { setFields(fieldsFrom(shop)); setError(""); setSaved(false); }}>{t("sellerShop.discard")}</button>
            <p role="status" className="text-xs text-muted-foreground">{t(dirty ? "sellerShop.unsaved" : "sellerShop.upToDate")}</p>
          </div>
        </fieldset>
      </form>
      <aside className="min-w-0 space-y-5 lg:sticky lg:top-6">
        <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="text-sm font-medium">{t("sellerShop.preview")}</h3><span className="rounded-full border border-border px-3 py-1 text-xs text-muted-foreground">{t(dirty ? "sellerShop.previewUnsaved" : "sellerShop.previewSaved")}</span></div>
        <ShopPreview fields={fields} category={categoryName} />
        <p className="text-xs leading-6 text-muted-foreground">{t("sellerShop.previewHint")}</p>
        <section className="rounded-2xl border border-border p-5"><h3 className="font-medium">{t("sellerShop.productsTitle")}</h3><p className="mt-2 text-sm leading-6 text-muted-foreground">{t("sellerShop.productsHint")}</p>
          <div className="mt-4 flex flex-wrap gap-3"><Link className={`${buttonClass} bg-background`} to="/seller/products">{t("sellerShop.products")}</Link><Link className={buttonClass} to="/seller/products/new">{t("sellerShop.addProduct")}</Link></div>
        </section>
      </aside>
    </div>}
  </main>;
}
