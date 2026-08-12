import { NavLink } from 'react-router-dom';
import { Smartphone } from 'lucide-react';
import { NAV_GROUPS } from '../../config/navigation';
import { useI18n } from '../../i18n/I18nProvider';
import { APP } from '@shared/constants/app';

/** Left navigation rail. Items are generated from the navigation config. */
export function Sidebar(): JSX.Element {
  const { t } = useI18n();

  return (
    <aside className="flex w-64 shrink-0 flex-col border-e border-slate-200 bg-white dark:border-surface-border dark:bg-surface-raised">
      <div className="flex items-center gap-3 px-5 py-5">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-500 text-white">
          <Smartphone size={20} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold">{APP.NAME}</div>
          <div className="text-xs text-slate-500 dark:text-slate-400">{t('app.tagline')}</div>
        </div>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 pb-6">
        {NAV_GROUPS.map((group) => (
          <div key={group.labelKey}>
            <div className="px-3 pb-2 text-xs font-medium uppercase tracking-wider text-slate-400 dark:text-slate-500">
              {t(group.labelKey)}
            </div>
            <ul className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                return (
                  <li key={item.id}>
                    <NavLink
                      to={item.path}
                      end={item.path === '/'}
                      className={({ isActive }) =>
                        'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ' +
                        (isActive
                          ? 'bg-brand-500/10 text-brand-600 dark:bg-brand-500/15 dark:text-brand-200'
                          : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-surface-overlay')
                      }
                    >
                      <Icon size={18} />
                      <span>{t(item.labelKey)}</span>
                    </NavLink>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-slate-200 px-5 py-3 text-xs text-slate-400 dark:border-surface-border dark:text-slate-500">
        v{APP.VERSION}
      </div>
    </aside>
  );
}
