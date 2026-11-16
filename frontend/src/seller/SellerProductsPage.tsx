import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ApiError } from "../auth/api";
import { deleteProduct, deleteProductImage, getCategories, getProduct, getProducts, productImageUrl, productStatuses, saveProduct, uploadProductImage,
  type Category, type Page, type Product, type ProductFields, type ProductStatus } from "./productsApi";

const inputClass = "w-full rounded-xl border border-border bg-background px-3 py-2.5";
const buttonClass = "inline-flex min-h-11 items-center justify-center rounded-xl border border-border px-4 py-2 text-sm disabled:opacity-50";
const primaryClass = `${buttonClass} bg-primary text-primary-foreground`;

function errorKey(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "PRODUCT_IN_USE") return "inUse";
    if (error.code === "CATEGORY_UNAVAILABLE") return "categoryUnavailable";
    if (error.status === 404) return "notFound";
    if (error.status === 403) return "forbidden";
    if (error.status === 413 || error.code === "INVALID_PRODUCT_IMAGE") return "imageError";
    if (error.status === 422) return "validationError";
  }
  return "requestError";
}

export function SellerProductsPage() {
  const { t } = useTranslation();
  const [page, setPage] = useState(0);
  const [status, setStatus] = useState("");
  const [data, setData] = useState<Page<Product> | null>(null);
  const [error, setError] = useState("");
  const [reload, setReload] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null); setError("");
    getProducts(page, status).then((result) => { if (active) setData(result); })
      .catch((reason) => { if (active) setError(errorKey(reason)); });
    return () => { active = false; };
  }, [page, status, reload]);
  return <section className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <h2 className="font-display text-3xl">{t("sellerProducts.title")}</h2>
      <Link className={primaryClass} to="/seller/products/new">{t("sellerProducts.add")}</Link>
    </div>
    <label className="block max-w-xs space-y-2"><span>{t("sellerProducts.filter")}</span>
      <select className={inputClass} value={status} onChange={(event) => { setPage(0); setStatus(event.target.value); }}>
        <option value="">{t("sellerProducts.all")}</option>
        {productStatuses.map((value) => <option key={value} value={value}>{t(`sellerProducts.status.${value}`)}</option>)}
      </select>
    </label>
    {error && <div role="alert" className="space-y-3"><p>{t(`sellerProducts.${error}`)}</p><button className={buttonClass} onClick={() => setReload((value) => value + 1)}>{t("sellerProducts.retry")}</button></div>}
    {!data && !error && <p role="status">{t("sellerProducts.loading")}</p>}
    {data && <>
      {data.items.length === 0 ? <p>{t("sellerProducts.empty")}</p> : <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {data.items.map((product) => <li key={product.id} className="overflow-hidden rounded-2xl border border-border bg-background">
          {product.images[0] && <img className="aspect-[4/3] w-full object-cover" src={productImageUrl(product.images[0].url)} alt={product.name} />}
          <div className="space-y-3 p-5">
            <h3 className="break-words font-display text-xl">{product.name}</h3>
            <p className="text-sm">{t(`sellerProducts.status.${product.status}`)}</p>
            <p>{t("sellerProducts.price")}: <bdi>{product.price}</bdi> · {t("sellerProducts.stock")}: {product.stock}</p>
            <Link className={buttonClass} to={`/seller/products/${product.id}`}>{t("sellerProducts.edit")}</Link>
          </div>
        </li>)}
      </ul>}
      <nav className="flex flex-wrap items-center gap-3" aria-label={t("sellerProducts.pagination")}>
        <button className={buttonClass} disabled={page === 0} onClick={() => setPage(page - 1)}>{t("sellerProducts.previous")}</button>
        <span>{t("sellerProducts.page", { current: page + 1, total: Math.max(1, Math.ceil(data.total / 20)) })}</span>
        <button className={buttonClass} disabled={(page + 1) * 20 >= data.total} onClick={() => setPage(page + 1)}>{t("sellerProducts.next")}</button>
      </nav>
    </>}
  </section>;
}

const initialFields: ProductFields = { name: "", description: "", category_id: "", price: "", stock: 0, status: "DRAFT" };

export function SellerProductFormPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [fields, setFields] = useState<ProductFields>(initialFields);
  const [product, setProduct] = useState<Product | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const uploadRef = useRef<HTMLInputElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const deleteRef = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (confirm) cancelRef.current?.focus(); }, [confirm]);
  useEffect(() => {
    let active = true;
    setLoading(true); setLoadError(""); setError(""); setMessage(""); setConfirm(null);
    Promise.all([getCategories(), productId ? getProduct(productId) : Promise.resolve(null)])
      .then(([options, result]) => {
        if (!active) return;
        setCategories(options); setProduct(result); setFields(result ? {
          name: result.name, description: result.description ?? "", category_id: result.category_id,
          price: result.price, stock: result.stock, status: result.status,
        } : { ...initialFields });
      }).catch((reason) => { if (active) setLoadError(errorKey(reason)); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [productId, reload]);
  const setField = <K extends keyof ProductFields>(name: K, value: ProductFields[K]) => setFields((current) => ({ ...current, [name]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault(); setError(""); setMessage("");
    if (!fields.name.trim() || !/^\d{1,10}(\.\d{1,2})?$/.test(fields.price) || !Number.isInteger(fields.stock) || fields.stock < 0 || !fields.category_id) {
      setError("validationError"); return;
    }
    setBusy(true);
    try {
      const result = await saveProduct({ ...fields, description: fields.description?.trim() || null }, productId);
      if (!productId) navigate(`/seller/products/${result.id}`, { replace: true });
      else { setProduct(result); setMessage("saved"); }
    } catch (reason) { setError(errorKey(reason)); }
    finally { setBusy(false); }
  }

  async function upload(file: File | undefined) {
    if (!file || !productId) return;
    setError(""); setMessage("");
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5 * 1024 * 1024 || file.size === 0) {
      setError("imageError"); if (uploadRef.current) uploadRef.current.value = ""; return;
    }
    setBusy(true);
    try {
      const image = await uploadProductImage(productId, file);
      setProduct((current) => current ? { ...current, images: [...current.images, image] } : current);
      setMessage("imageAdded");
    } catch (reason) { setError(errorKey(reason)); }
    finally { setBusy(false); if (uploadRef.current) uploadRef.current.value = ""; }
  }

  async function remove() {
    if (!productId || !confirm) return;
    setBusy(true); setError(""); setMessage("");
    try {
      if (confirm === "product") { await deleteProduct(productId); navigate("/seller/products"); }
      else {
        await deleteProductImage(productId, confirm);
        setProduct((current) => current ? { ...current, images: current.images.filter((image) => image.id !== confirm) } : current);
        setMessage("imageRemoved");
      }
      setConfirm(null);
    } catch (reason) { setError(errorKey(reason)); }
    finally { setBusy(false); }
  }

  function cancelDelete() { setConfirm(null); deleteRef.current?.focus(); }
  return <section className="max-w-3xl space-y-6">
    <Link className="text-sm underline underline-offset-4" to="/seller/products">{t("sellerProducts.back")}</Link>
    <h2 className="font-display text-3xl">{t(productId ? "sellerProducts.editTitle" : "sellerProducts.add")}</h2>
    {loading && <p role="status">{t("sellerProducts.loading")}</p>}
    {loadError && <div role="alert"><p>{t(`sellerProducts.${loadError}`)}</p><button className={buttonClass} onClick={() => setReload((value) => value + 1)}>{t("sellerProducts.retry")}</button></div>}
    {error && <p role="alert">{t(`sellerProducts.${error}`)}</p>}
    {message && <p role="status">{t(`sellerProducts.${message}`)}</p>}
    {!loading && !loadError && <>
      <form onSubmit={submit} className="rounded-2xl border border-border p-5 sm:p-7">
        <fieldset disabled={busy || confirm !== null} className="space-y-5">
          <label className="block space-y-2"><span>{t("sellerProducts.name")}</span><input required maxLength={255} className={inputClass} value={fields.name} onChange={(e) => setField("name", e.target.value)} /></label>
          <label className="block space-y-2"><span>{t("sellerProducts.description")}</span><textarea rows={5} maxLength={10000} className={inputClass} value={fields.description ?? ""} onChange={(e) => setField("description", e.target.value)} /></label>
          <label className="block space-y-2"><span>{t("sellerProducts.category")}</span><select required className={inputClass} value={fields.category_id} onChange={(e) => setField("category_id", e.target.value)}>
            <option value="">{t("sellerProducts.chooseCategory")}</option>
            {fields.category_id && !categories.some((item) => item.id === fields.category_id) && <option value={fields.category_id}>{t("sellerProducts.existingCategory")}</option>}
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select></label>
          {categories.length === 0 && <p role="status">{t("sellerProducts.noCategories")}</p>}
          <div className="grid gap-5 sm:grid-cols-2">
            <label className="block space-y-2"><span>{t("sellerProducts.price")}</span><input required inputMode="decimal" dir="ltr" pattern="[0-9]{1,10}(\.[0-9]{1,2})?" className={inputClass} value={fields.price} onChange={(e) => setField("price", e.target.value)} /></label>
            <label className="block space-y-2"><span>{t("sellerProducts.stock")}</span><input required type="number" min={0} max={2147483647} step={1} className={inputClass} value={Number.isNaN(fields.stock) ? "" : fields.stock} onChange={(e) => setField("stock", e.target.value === "" ? NaN : Number(e.target.value))} /></label>
          </div>
          <label className="block space-y-2"><span>{t("sellerProducts.statusLabel")}</span><select className={inputClass} value={fields.status} onChange={(e) => setField("status", e.target.value as ProductStatus)}>
            {productStatuses.map((value) => <option key={value} value={value}>{t(`sellerProducts.status.${value}`)}</option>)}
          </select></label>
          <p className="text-sm text-muted-foreground">{t("sellerProducts.publishHint")}</p>
          <button className={primaryClass} type="submit">{t(busy ? "sellerProducts.working" : "sellerProducts.save")}</button>
        </fieldset>
      </form>
      <section className="space-y-4 rounded-2xl border border-border p-5 sm:p-7" aria-label={t("sellerProducts.images")}>
        <h3 className="text-xl">{t("sellerProducts.images")}</h3>
        <p className="text-sm text-muted-foreground">{t(product ? "sellerProducts.imageHint" : "sellerProducts.saveBeforeImages")}</p>
        {product && <>
          <label className="block space-y-2"><span>{t("sellerProducts.upload")}</span><input ref={uploadRef} type="file" accept="image/jpeg,image/png,image/webp" disabled={busy || confirm !== null} onChange={(e) => void upload(e.target.files?.[0])} className="block w-full text-sm" /></label>
          {product.images.length === 0 && <p>{t("sellerProducts.noImages")}</p>}
          <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3">{product.images.map((image, index) => <li key={image.id} className="space-y-2">
            <img className="aspect-square w-full rounded-xl object-cover" src={productImageUrl(image.url)} alt={t("sellerProducts.imageAlt", { name: product.name, number: index + 1 })} />
            <button type="button" className={buttonClass} disabled={busy || confirm !== null} onClick={() => setConfirm(image.id)}>{t("sellerProducts.removeImage", { number: index + 1 })}</button>
          </li>)}</ul>
        </>}
      </section>
      {product && <button ref={deleteRef} type="button" className={`${buttonClass} text-red-700`} disabled={busy || confirm !== null} onClick={() => setConfirm("product")}>{t("sellerProducts.delete")}</button>}
      {confirm && <div role="dialog" aria-labelledby="delete-title" className="space-y-4 rounded-2xl border border-border bg-background p-5" onKeyDown={(e) => { if (e.key === "Escape" && !busy) cancelDelete(); }}>
        <h3 id="delete-title" className="text-lg font-medium">{t(confirm === "product" ? "sellerProducts.confirmDelete" : "sellerProducts.confirmImageDelete")}</h3>
        <div className="flex flex-wrap gap-3"><button type="button" className={primaryClass} disabled={busy} onClick={() => void remove()}>{t(busy ? "sellerProducts.working" : "sellerProducts.confirm")}</button>
          <button type="button" ref={cancelRef} className={buttonClass} disabled={busy} onClick={cancelDelete}>{t("sellerProducts.cancel")}</button></div>
      </div>}
    </>}
  </section>;
}
