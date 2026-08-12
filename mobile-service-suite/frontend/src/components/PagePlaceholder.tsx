import { Card } from './ui/Card';
import { useI18n } from '../i18n/I18nProvider';
import type { NavItem } from '../config/navigation';

/** Standard "work in progress" page rendered for sections not yet implemented. */
export function PagePlaceholder({ item }: { item: NavItem }): JSX.Element {
  const { t } = useI18n();
  const Icon = item.icon;

  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/10 text-brand-600 dark:bg-brand-500/15 dark:text-brand-200">
          <Icon size={22} />
        </div>
        <h1 className="text-2xl font-semibold">{t(item.labelKey)}</h1>
      </div>

      <Card>
        <div className="flex flex-col items-start gap-2">
          <span className="rounded-full bg-status-warning/15 px-3 py-1 text-xs font-medium text-status-warning">
            {t('page.wipTitle')}
          </span>
          <p className="text-slate-600 dark:text-slate-300">
            {t('page.wipBody', { phase: item.phase })}
          </p>
        </div>
      </Card>
    </div>
  );
}
