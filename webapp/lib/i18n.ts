import en from "@/src/locales/en.json"
import ru from "@/src/locales/ru.json"

type TranslationMap = Record<string, any>

const translations: Record<string, TranslationMap> = {
  en: en as TranslationMap,
  ru: ru as TranslationMap
}

function getFromPath(obj: TranslationMap, path: string): any {
  const parts = path.split(".")
  let cur: any = obj
  for (const p of parts) {
    if (cur == null || typeof cur !== "object" || !(p in cur)) return undefined
    cur = cur[p]
  }
  return cur
}

export function translate(lang: string | undefined, key: string, vars?: Record<string, string | number>): string {
  const normalized = (lang || "en").slice(0, 2)
  const dict = translations[normalized] || translations.en
  const fallbackDict = translations.en

  let template = getFromPath(dict, key) ?? getFromPath(fallbackDict, key) ?? key

  if (typeof template !== "string") {
    template = key
  }

  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      template = template.replace(new RegExp(`\\{${k}\\}`, "g"), String(v))
    }
  }

  return template
}

export type TFunc = (key: string, vars?: Record<string, string | number>) => string

export function getLocaleValue(lang: string | undefined, key: string): any {
  const normalized = (lang || "en").slice(0, 2)
  const dict = translations[normalized] || translations.en
  const fallbackDict = translations.en
  const val = getFromPath(dict, key)
  if (val !== undefined) return val
  return getFromPath(fallbackDict, key)
}
