import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { SUPPORTED_LOCALES, type Locale } from '@shared/constants/app';
import type { Dictionary, TranslationKey } from './keys';
import { en } from './locales/en';
import { ar } from './locales/ar';
import { it } from './locales/it';

const DICTIONARIES: Record<Locale, Dictionary> = { en, ar, it };
const RTL_LOCALES: ReadonlySet<Locale> = new Set<Locale>(['ar']);
const STORAGE_KEY = 'mss.locale';

type TranslateParams = Record<string, string | number>;

interface I18nContextValue {
  locale: Locale;
  dir: 'ltr' | 'rtl';
  setLocale: (locale: Locale) => void;
  availableLocales: readonly Locale[];
  t: (key: TranslationKey, params?: TranslateParams) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function readInitialLocale(): Locale {
  if (typeof localStorage !== 'undefined') {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && (SUPPORTED_LOCALES as readonly string[]).includes(stored)) {
      return stored as Locale;
    }
  }
  return 'en';
}

export function I18nProvider({ children }: { children: ReactNode }): JSX.Element {
  const [locale, setLocaleState] = useState<Locale>(readInitialLocale);

  const dir: 'ltr' | 'rtl' = RTL_LOCALES.has(locale) ? 'rtl' : 'ltr';

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = locale;
      document.documentElement.dir = dir;
    }
  }, [locale, dir]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    if (typeof localStorage !== 'undefined') localStorage.setItem(STORAGE_KEY, next);
  }, []);

  const t = useCallback(
    (key: TranslationKey, params?: TranslateParams): string => {
      const template = DICTIONARIES[locale][key];
      if (!params) return template;
      return template.replace(/\{(\w+)\}/g, (_match, name: string) =>
        name in params ? String(params[name]) : `{${name}}`,
      );
    },
    [locale],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ locale, dir, setLocale, availableLocales: SUPPORTED_LOCALES, t }),
    [locale, dir, setLocale, t],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within an I18nProvider');
  return ctx;
}
