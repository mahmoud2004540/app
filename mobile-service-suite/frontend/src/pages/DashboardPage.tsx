import { useDeviceStatus } from '../hooks/useDeviceStatus';
import { DeviceOverviewCard } from '../components/dashboard/DeviceOverviewCard';
import { DeviceInfoGrid } from '../components/dashboard/DeviceInfoGrid';
import { ProtectionStatus } from '../components/dashboard/ProtectionStatus';
import { QuickActions } from '../components/dashboard/QuickActions';
import { ConnectionChecklist } from '../components/dashboard/ConnectionChecklist';

/**
 * PHASE 3 — Main Dashboard.
 *
 * Composes the device overview, information grid, protection/status panel,
 * quick actions and (when nothing is connected) the connection checklist. Wired
 * to `useDeviceStatus`, which becomes a live ADB/Fastboot probe in PHASE 5.
 */
export function DashboardPage(): JSX.Element {
  const { state, device, availability, detect } = useDeviceStatus();
  const connected = device !== null;

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <DeviceOverviewCard device={device} state={state} onDetect={detect} />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <DeviceInfoGrid device={device} />
        </div>
        <div>
          {connected ? (
            <ProtectionStatus device={device} />
          ) : (
            <ConnectionChecklist availability={availability} />
          )}
        </div>
      </div>

      <QuickActions onDetect={detect} detecting={state === 'detecting'} />
    </div>
  );
}
