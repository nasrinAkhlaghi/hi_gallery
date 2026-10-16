import { useTranslation } from "react-i18next";

export function LanguageSwitcher({
  className = "",
  onLanguageChange,
}: {
  className?: string;
  onLanguageChange?: () => void;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage?.startsWith("fa") ? "fa" : "en";

  return (
    <select
      aria-label={t("language.select")}
      className={`min-h-11 rounded-full border border-border bg-background px-3 text-sm text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-primary ${className}`}
      dir={language === "fa" ? "rtl" : "ltr"}
      value={language}
      onChange={(event) => {
        void i18n.changeLanguage(event.target.value);
        onLanguageChange?.();
      }}
    >
      <option value="en">{t("language.english", { lng: "en" })}</option>
      <option value="fa">{t("language.persian", { lng: "fa" })}</option>
    </select>
  );
}
