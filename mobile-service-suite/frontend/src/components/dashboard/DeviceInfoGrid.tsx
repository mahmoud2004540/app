import { Card } from '../ui/Card';
import { useI18n } from '../../i18n/I18nProvider';
import type { TranslationKey } from '../../i18n/keys';
import type { DeviceSnapshot } from '../../types/device';

const PLACEHOLDER = '—';

interface DeviceInfoGridProps {
  device: DeviceSnapshot | null;
}

/** Read-only grid of the device's identifying information. */
export function DeviceInfoGrid({ device }: DeviceInfoGridProps): JSX.Element {
  const { t } = useI18n();

  const rows: ReadonlyArray<[TranslationKey, string]> = [
    ['device.brand', device?.brand ?? PLACEHOLDER],
    ['device.model', device?.model ?? PLACEHOLDER],
    ['device.imei', device?.imei ?? PLACEHOLDER],
    ['device.serial', device?.serial ?? PLACEHOLDER],
    ['device.android', device?.androidVersion ?? PLACEHOLDER],
    ['device.build', device?.buildNumber ?? PLACEHOLDER],
    ['device.cpu', device?.cpu ?? PLACEHOLDER],
    ['device.ram', device?.ram ?? PLACEHOLDER],
    ['device.storage', device?.storage ?? PLACEHOLDER],
    ['device.usbMode', device?.usbMode ?? PLACEHOLDER],
    [
      'device.battery',
      device ? `${device.batteryPercent}%` : PLACEHOLDER,
    ],
  ];

  return (
    <Card>
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {t('dash.deviceInformation')}
      </h2>
      <dl className="grid grid-cols-1 gap-x-8 gap-y-3 sm:grid-cols-2">
        {rows.map(([key, value]) => (
          <div key={key} className="flex items-center justify-between gap-4 border-b border-slate-100 pb-2 dark:border-surface-border/60">
            <dt className="text-sm text-slate-500 dark:text-slate-400">{t(key)}</dt>
            <dd className="truncate font-mono text-sm text-slate-800 dark:text-slate-100">{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}
