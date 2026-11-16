import { apiRequest } from "../auth/api";

export type ProductStatus = "DRAFT" | "ACTIVE" | "INACTIVE" | "SOLD_OUT";
export const productStatuses: ProductStatus[] = ["DRAFT", "ACTIVE", "INACTIVE", "SOLD_OUT"];
export type ProductImage = { id: string; url: string; sort_order: number };
export type ProductFields = {
  name: string; description: string | null; category_id: string; price: string; stock: number; status: ProductStatus;
};
export type Product = ProductFields & { id: string; images: ProductImage[]; created_at: string; updated_at: string };
export type Category = { id: string; parent_id: string | null; name: string; slug: string };
export type Page<T> = { items: T[]; total: number; page: number; page_size: number };

export function getProducts(page: number, status: string) {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (status) params.set("status", status);
  return apiRequest<Page<Product>>(`/seller/products?${params}`);
}

export async function getCategories(): Promise<Category[]> {
  const items: Category[] = [];
  for (let page = 0; ; page += 1) {
    const result = await apiRequest<Page<Category>>(`/categories?page=${page}&page_size=100`);
    items.push(...result.items);
    if (items.length >= result.total || result.items.length === 0) return items;
  }
}

export const getProduct = (id: string) => apiRequest<Product>(`/seller/products/${encodeURIComponent(id)}`);
export const saveProduct = (values: ProductFields, id?: string) => apiRequest<Product>(
  id ? `/seller/products/${encodeURIComponent(id)}` : "/seller/products",
  { method: id ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) },
);
export const deleteProduct = (id: string) => apiRequest<void>(`/seller/products/${encodeURIComponent(id)}`, { method: "DELETE" });
export const uploadProductImage = (id: string, file: File) => apiRequest<ProductImage>(`/seller/products/${encodeURIComponent(id)}/images`, {
  method: "POST", headers: { "Content-Type": file.type }, body: file,
});
export const deleteProductImage = (id: string, imageId: string) => apiRequest<void>(
  `/seller/products/${encodeURIComponent(id)}/images/${encodeURIComponent(imageId)}`, { method: "DELETE" },
);

export function productImageUrl(path: string): string {
  const base = import.meta.env.VITE_API_BASE_URL || "/api/v1";
  return new URL(path, new URL(base, window.location.origin)).href;
}
