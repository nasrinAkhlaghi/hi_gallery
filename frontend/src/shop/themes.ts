export const shopThemeIds = ["gallery", "linen", "clay"] as const;
export type ShopThemeId = typeof shopThemeIds[number];

// Presets stay scoped to shop presentation, independent from the Studio theme.
export const shopThemes = {
  gallery: { background: "#faf6ef", surface: "#fffdf9", text: "#352b24", muted: "#705e50", accent: "#884c36", border: "#d8c7b4" },
  linen: { background: "#f4f5f1", surface: "#ffffff", text: "#29342e", muted: "#56665c", accent: "#3e5b4c", border: "#ccd5cd" },
  clay: { background: "#f3e5da", surface: "#fcf6f0", text: "#422b25", muted: "#77584c", accent: "#90462f", border: "#cdb09b" },
} satisfies Record<ShopThemeId, { background: string; surface: string; text: string; muted: string; accent: string; border: string }>;
