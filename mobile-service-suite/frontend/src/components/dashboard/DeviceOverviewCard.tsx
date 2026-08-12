import { Smartphone, SmartphoneNfc } from 'lucide-react';
import { Card } from '../ui/Card';
import { Button } from '../ui/Button';
import { StatusPill } from '../ui/StatusPill';
import { useI18n } from '../../i18n/I18nProvider';
import type { DetectionState, DeviceSnapshot } from '../../types/device';

interface DeviceOverviewCardProps {
  device: DeviceSnapshot | null;
  state: DetectionState;
  onDetect: () => void;
}

/** Hero card: connection state, device identity, and the primary Detect action. */
export function DeviceOverviewCard({
  device,
  state,
  onDetect,
}: DeviceOverviewCardProps): JSX.Element {
  const { t } = useI18n();
  const connected = device !== null;
  const detecting = state === 'detecting';

  return (
    <Card className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-4">
        <div
          className={
            'flex h-14 w-14 items-center justify-center rounded-xl ' +
            (connected
              ? 'bg-status-good/15 text-status-good'
              : 'bg-slate-200 text-slate-400 dark:bg-surface-overlay dark:text-slate-500')
          }
        >
          {connected ? <SmartphoneNfc size={26} /> : <Smartphone size={26} />}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">
              {connected ? `${device.brand} ${device.model}` : t('dash.notConnected')}
            </h1>
            <StatusPill tone={connected ? 'good' : 'neutral'}>
              {connected ? t('dash.connected') : t('status.disconnected')}
            </StatusPill>
          </div>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {connected ? t('dash.previewNote') : t('dash.connectPrompt')}
          </p>
        </div>
      </div>

      <Button onClick={onDetect} disabled={detecting}>
        {detecting ? t('dash.detecting') : t('dash.detect')}
      </Button>
    </Card>
  );
}
