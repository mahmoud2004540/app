import { HelpCircle } from 'lucide-react';
import { Card } from '../ui/Card';
import { StatusPill } from '../ui/StatusPill';
import { useI18n } from '../../i18n/I18nProvider';
import type { TranslationKey } from '../../i18n/keys';

const CHECKS: readonly TranslationKey[] = [
  'dash.check.usbCable',
  'dash.check.usbPort',
  'dash.check.drivers',
  'dash.check.adb',
  'dash.check.fastboot',
];

/**
 * Shown when no device is detected: the connection troubleshooting checklist.
 * Each item is "unknown" until live checks are implemented in PHASE 5.
 */
export function ConnectionChecklist(): JSX.Element {
  const { t } = useI18n();

  return (
    <Card>
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {t('dash.checklistTitle')}
      </h2>
      <ul className="space-y-3">
        {CHECKS.map((key) => (
          <li key={key} className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
              <HelpCircle size={16} className="text-slate-400" />
              {t(key)}
            </span>
            <StatusPill tone="neutral">{t('status.unknown')}</StatusPill>
          </li>
        ))}
      </ul>
    </Card>
  );
}
