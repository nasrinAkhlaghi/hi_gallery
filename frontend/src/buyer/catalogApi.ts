import type { Category, Page, ProductImage } from "../seller/productsApi";
import type { ShopThemeId } from "../shop/themes";
export { getCategories } from "../seller/productsApi";
export type { Category, Page };

export type PublicProduct = {
  id: string; name: string; description: string | null; category: Category;
  price: string; stock: number; status: "ACTIVE" | "SOLD_OUT"; images: ProductImage[];
  seller: { id: string; shop_name: string };
};
export type PublicShop = {
  id: string; shop_name: string; description: string | null; logo_url: string | null;
  category: Category | null; theme_id: ShopThemeId;
};

export function productListPath(page: number, category: string, q = "", sellerId?: string) {
  const params = new URLSearchParams({ page: String(page), page_size: "20" });
  if (category) params.set("category_id", category);
  if (q && !sellerId) params.set("q", q);
  return `${sellerId ? `/shops/${encodeURIComponent(sellerId)}/products` : "/products"}?${params}`;
}

export const categoryLink = (id: string) => `/browse?${new URLSearchParams({ category_id: id })}`;
