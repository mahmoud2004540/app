import { Card } from '../ui/Card';
import { StatusPill, type StatusTone } from '../ui/StatusPill';
import { useI18n } from '../../i18n/I18nProvider';
import type { TranslationKey } from '../../i18n/keys';
import type { DeviceSnapshot, TriState } from '../../types/device';

interface ProtectionStatusProps {
  device: DeviceSnapshot | null;
}

interface Row {
  labelKey: TranslationKey;
  valueKey: TranslationKey;
  tone: StatusTone;
}

function connectionRow(labelKey: TranslationKey, connected: boolean | undefined): Row {
  if (connected === undefined) {
    return { labelKey, valueKey: 'status.unknown', tone: 'neutral' };
  }
  return connected
    ? { labelKey, valueKey: 'status.connected', tone: 'good' }
    : { labelKey, valueKey: 'status.disconnected', tone: 'neutral' };
}

/** Locks are reported only: FRP is diagnosed, never bypassed (see SECURITY.md). */
function lockRow(labelKey: TranslationKey, tri: TriState | undefined): Row {
  if (tri === undefined || tri === 'unknown') {
    return { labelKey, valueKey: 'status.unknown', tone: 'neutral' };
  }
  return tri === 'yes'
    ? { labelKey, valueKey: 'status.unlocked', tone: 'warning' }
    : { labelKey, valueKey: 'status.locked', tone: 'good' };
}

function frpRow(tri: TriState | undefined): Row {
  if (tri === undefined || tri === 'unknown') {
    return { labelKey: 'status.frp', valueKey: 'status.unknown', tone: 'neutral' };
  }
  return tri === 'yes'
    ? { labelKey: 'status.frp', valueKey: 'status.protected', tone: 'warning' }
    : { labelKey: 'status.frp', valueKey: 'status.unprotected', tone: 'good' };
}

export function ProtectionStatus({ device }: ProtectionStatusProps): JSX.Element {
  const { t } = useI18n();

  const rows: Row[] = [
    connectionRow('status.adb', device?.adbConnected),
    connectionRow('status.fastboot', device?.fastbootConnected),
    lockRow('status.bootloader', device?.bootloaderUnlocked),
    lockRow('status.oemLock', device?.oemUnlocked),
    frpRow(device?.frpLocked),
  ];

  return (
    <Card>
      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
        {t('dash.protectionStatus')}
      </h2>
      <ul className="space-y-3">
        {rows.map((row) => (
          <li key={row.labelKey} className="flex items-center justify-between">
            <span className="text-sm text-slate-600 dark:text-slate-300">{t(row.labelKey)}</span>
            <StatusPill tone={row.tone}>{t(row.valueKey)}</StatusPill>
          </li>
        ))}
      </ul>
    </Card>
  );
}
