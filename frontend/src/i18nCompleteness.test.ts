import { describe, expect, it } from "vitest";
import { phrases } from "./phrases";

const productionUi = import.meta.glob(
  ["./pages/**/*.tsx", "./components/**/*.tsx", "!**/*.test.tsx"],
  { eager: true, import: "default", query: "?raw" },
) as Record<string, string>;

describe("i18n completeness", () => {
  it("provides all five translations for every phrase", () => {
    for (const translations of Object.values(phrases)) {
      expect(translations).toHaveLength(5);
      translations.forEach((value) => expect(value.trim()).not.toBe(""));
      expect(translations[2]).not.toMatch(/\p{Script=Han}/u);
    }
  });

  it("keeps Chinese literals out of production UI code", () => {
    for (const [path, source] of Object.entries(productionUi)) {
      const withoutLanguageNames = source
        .replaceAll("繁體中文", "")
        .replaceAll("簡體中文", "")
        .replaceAll("简体中文", "")
        .replaceAll("日本語", "");
      expect(withoutLanguageNames, path).not.toMatch(/\p{Script=Han}/u);
    }
  });
});
