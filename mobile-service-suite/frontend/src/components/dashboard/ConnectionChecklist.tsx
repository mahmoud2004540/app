import { HelpCircle, CheckCircle2, XCircle } from 'lucide-react';
import { Card } from '../ui/Card';
import { StatusPill, type StatusTone } from '../ui/StatusPill';
import { useI18n } from '../../i18n/I18nProvider';
import type { TranslationKey } from '../../i18n/keys';
import type { ToolAvailability } from '../../hooks/useDeviceStatus';
import type { TriState } from '../../types/device';

interface ConnectionChecklistProps {
  availability?: ToolAvailability;
}

interface Check {
  key: TranslationKey;
  tri: TriState;
}

function toneFor(tri: TriState): StatusTone {
  if (tri === 'yes') return 'good';
  if (tri === 'no') return 'error';
  return 'neutral';
}

function valueKey(tri: TriState): TranslationKey {
  if (tri === 'yes') return 'status.connected';
  if (tri === 'no') return 'status.disconnected';
  return 'status.unknown';
}

/**
 * Shown when no device is detected: the connection troubleshooting checklist.
 * ADB and Fastboot reflect real tool availability; the USB checks remain
 * physical/manual and are surfaced as informational.
 */
export function ConnectionChecklist({ availability }: ConnectionChecklistProps): JSX.Element {
  const { t } = useI18n();
  const adb = availability?.adb ?? 'unknown';
  const fastboot = availability?.fastboot ?? 'unknown';

  const checks: Check[] = [
    { key: 'dash.check.usbCable', tri: 'unknown' },
    { key: 'dash.check.usbPort', tri: 'unknown' },
    { key: 'dash.check.drivers', tri: 'unknown' },
    { key: 'dash.check.adb', tri: adb },
    { key: 'dash.check.fastboot', tri: fastboot },
  ];

  const iconFor = (tri: TriState): JSX.Element => {
    if (tri === 'yes') return <CheckCircle2 size={16} className="text-status-good" />;
    if (tri === 'no') return <XCircle size={16} className="text-status-error" />;
    return <HelpCircle size={16} className="text-slate-400" />;
  };

  return (
    <Card>
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {t('dash.checklistTitle')}
      </h2>
      <ul className="space-y-3">
        {checks.map((check) => (
          <li key={check.key} className="flex items-center justify-between">
            <span className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
              {iconFor(check.tri)}
              {t(check.key)}
            </span>
            <StatusPill tone={toneFor(check.tri)}>{t(valueKey(check.tri))}</StatusPill>
          </li>
        ))}
      </ul>
    </Card>
  );
}
