import { apiRequest } from "../auth/api";
import type { ShopThemeId } from "../shop/themes";

export type ShopFields = {
  shop_name: string;
  description: string | null;
  logo_url: string | null;
  shop_category_id: string | null;
  theme_id: ShopThemeId;
};
export type ShopSettings = ShopFields & { id: string; updated_at: string };

export const getShop = () => apiRequest<ShopSettings>("/seller/shop");
export const saveShop = (fields: ShopFields) => apiRequest<ShopSettings>("/seller/shop", {
  method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(fields),
});
