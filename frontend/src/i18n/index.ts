import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en/common.json";
import fa from "./locales/fa/common.json";

export type AppLanguage = "en" | "fa";

const LANGUAGE_STORAGE_KEY = "hi-gallery-language";

function readSavedLanguage(): AppLanguage {
  try {
    const savedLanguage = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return savedLanguage === "fa" ? "fa" : "en";
  } catch {
    return "en";
  }
}

function syncDocument(language: string) {
  if (typeof document === "undefined") return;
  const appLanguage: AppLanguage = language.startsWith("fa") ? "fa" : "en";
  document.documentElement.lang = appLanguage;
  document.documentElement.dir = appLanguage === "fa" ? "rtl" : "ltr";
  document.title = i18n.t("app.documentTitle", { lng: appLanguage });
  document
    .querySelector<HTMLMetaElement>('meta[name="description"]')
    ?.setAttribute("content", i18n.t("app.description", { lng: appLanguage }));
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { common: en },
    fa: { common: fa },
  },
  lng: readSavedLanguage(),
  fallbackLng: "en",
  supportedLngs: ["en", "fa"],
  defaultNS: "common",
  ns: ["common"],
  interpolation: { escapeValue: false },
  initAsync: false,
  react: { useSuspense: false },
});

i18n.on("languageChanged", (language) => {
  syncDocument(language);
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language.startsWith("fa") ? "fa" : "en");
  } catch {
    // Keep the in-memory language selection when browser storage is unavailable.
  }
});

syncDocument(i18n.resolvedLanguage ?? i18n.language ?? "en");

export default i18n;
