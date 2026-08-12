import { useCallback, useEffect, useState } from 'react';
import { Cable, RefreshCw, MonitorCog, ExternalLink, Info, ShieldAlert } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Modal } from '../components/ui/Modal';
import { StatusPill, type StatusTone } from '../components/ui/StatusPill';
import { useI18n } from '../i18n/I18nProvider';
import type { TranslationKey } from '../i18n/keys';
import type { DriverStatus } from '@shared/types/driver';

function statusView(d: DriverStatus): { tone: StatusTone; key: TranslationKey } {
  if (d.installed === 'yes') return { tone: 'good', key: 'drivers.statusInstalled' };
  if (d.installed === 'no') return { tone: 'neutral', key: 'drivers.statusNotInstalled' };
  return { tone: 'neutral', key: 'drivers.statusUnknown' };
}

export function DriversPage(): JSX.Element {
  const { t } = useI18n();
  const bridge = typeof window !== 'undefined' ? window.mss : undefined;

  const [drivers, setDrivers] = useState<DriverStatus[]>([]);
  const [loading, setLoading] = useState(false);
  const [info, setInfo] = useState<DriverStatus | null>(null);

  const refresh = useCallback(async () => {
    if (!bridge) return;
    setLoading(true);
    try {
      const report = await bridge.drivers.list();
      setDrivers(report.drivers);
    } finally {
      setLoading(false);
    }
  }, [bridge]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const openUrl = (url: string): void => {
    if (bridge) void bridge.system.openExternal(url);
    else if (typeof window !== 'undefined') window.open(url, '_blank', 'noopener');
  };

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-500/10 text-brand-600 dark:bg-brand-500/15 dark:text-brand-200">
          <Cable size={22} />
        </div>
        <div className="flex-1">
          <h1 className="text-2xl font-semibold">{t('nav.drivers')}</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">{t('drivers.subtitle')}</p>
        </div>
        <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          {t('adb.refresh')}
        </Button>
        <Button
          variant="secondary"
          onClick={() => bridge && void bridge.system.openDeviceManager()}
        >
          <MonitorCog size={16} />
          {t('drivers.openDeviceManager')}
        </Button>
      </div>

      {/* Consent banner */}
      <div className="flex items-start gap-3 rounded-xl border border-status-warning/30 bg-status-warning/10 p-4 text-sm text-slate-700 dark:text-slate-200">
        <ShieldAlert className="mt-0.5 shrink-0 text-status-warning" size={18} />
        <p>{t('drivers.noAutoInstall')}</p>
      </div>

      {drivers.length === 0 && !loading ? (
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">{t('drivers.needsApp')}</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {drivers.map((d) => {
            const status = statusView(d);
            return (
              <Card key={d.key} className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-semibold">{d.name}</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      {t('drivers.vendor')}: {d.vendor}
                    </p>
                  </div>
                  <StatusPill tone={status.tone}>{t(status.key)}</StatusPill>
                </div>

                <div className="flex flex-wrap gap-1">
                  {d.supportedBrands.map((b) => (
                    <span
                      key={b}
                      className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 dark:bg-surface-overlay dark:text-slate-400"
                    >
                      {b}
                    </span>
                  ))}
                </div>

                {d.version && (
                  <p className="font-mono text-xs text-slate-500 dark:text-slate-400">
                    {t('drivers.version')}: {d.version}
                  </p>
                )}

                <div className="mt-auto flex gap-2">
                  <Button onClick={() => openUrl(d.downloadUrl)}>
                    <ExternalLink size={15} />
                    {t('drivers.download')}
                  </Button>
                  <Button variant="ghost" onClick={() => setInfo(d)}>
                    <Info size={15} />
                    {t('drivers.info')}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Modal open={info !== null} onClose={() => setInfo(null)} title={info?.name ?? ''}>
        <p className="text-sm text-slate-600 dark:text-slate-300">{info?.description}</p>
        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">
          {t('drivers.supported')}: {info?.supportedBrands.join(', ')}
        </p>
        <div className="mt-4 flex justify-end">
          <Button onClick={() => info && openUrl(info.downloadUrl)}>
            <ExternalLink size={15} />
            {t('drivers.download')}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
