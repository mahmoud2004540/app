import { Bell, Moon, Search, Sun } from 'lucide-react';
import { useI18n } from '../../i18n/I18nProvider';
import { useTheme } from '../../theme/ThemeProvider';
import { SUPPORTED_LOCALES, type Locale } from '@shared/constants/app';

const LOCALE_LABELS: Record<Locale, string> = { en: 'EN', ar: 'ع', it: 'IT' };

/** Top application bar: search, device status, language, theme and notifications. */
export function TopBar(): JSX.Element {
  const { t, locale, setLocale } = useI18n();
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="flex h-16 shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-6 dark:border-surface-border dark:bg-surface-raised">
      <div className="relative max-w-md flex-1">
        <Search
          size={16}
          className="pointer-events-none absolute inset-y-0 start-3 my-auto text-slate-400"
        />
        <input
          type="search"
          placeholder={t('topbar.searchPlaceholder')}
          aria-label={t('topbar.searchPlaceholder')}
          className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2 ps-9 pe-3 text-sm outline-none transition-colors focus:border-brand-400 dark:border-surface-border dark:bg-surface-overlay dark:text-slate-100"
        />
      </div>

      <div className="ms-auto flex items-center gap-2">
        <span className="hidden items-center gap-2 rounded-full bg-slate-100 px-3 py-1.5 text-xs text-slate-500 dark:bg-surface-overlay dark:text-slate-400 sm:flex">
          <span className="h-2 w-2 rounded-full bg-slate-400" />
          {t('topbar.noDevice')}
        </span>

        <label className="sr-only" htmlFor="locale-select">
          {t('topbar.language')}
        </label>
        <select
          id="locale-select"
          value={locale}
          onChange={(e) => setLocale(e.target.value as Locale)}
          aria-label={t('topbar.language')}
          className="rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-sm outline-none focus:border-brand-400 dark:border-surface-border dark:bg-surface-overlay dark:text-slate-100"
        >
          {SUPPORTED_LOCALES.map((code) => (
            <option key={code} value={code}>
              {LOCALE_LABELS[code]}
            </option>
          ))}
        </select>

        <button
          type="button"
          onClick={toggleTheme}
          title={t('topbar.toggleTheme')}
          aria-label={t('topbar.toggleTheme')}
          className="rounded-lg border border-slate-200 p-2 text-slate-600 transition-colors hover:bg-slate-100 dark:border-surface-border dark:text-slate-300 dark:hover:bg-surface-overlay"
        >
          {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
        </button>

        <button
          type="button"
          title={t('topbar.notifications')}
          aria-label={t('topbar.notifications')}
          className="rounded-lg border border-slate-200 p-2 text-slate-600 transition-colors hover:bg-slate-100 dark:border-surface-border dark:text-slate-300 dark:hover:bg-surface-overlay"
        >
          <Bell size={18} />
        </button>
      </div>
    </header>
  );
}
