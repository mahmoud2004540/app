import { useCallback, useState } from 'react';
import type { DetectionState, DeviceSnapshot, TriState } from '../types/device';
import { pickPrimaryDevice, toSnapshot } from '../utils/deviceMapper';

export interface ToolAvailability {
  adb: TriState;
  fastboot: TriState;
}

interface UseDeviceStatus {
  state: DetectionState;
  device: DeviceSnapshot | null;
  availability: ToolAvailability;
  detect: () => void;
}

const UNKNOWN_AVAILABILITY: ToolAvailability = { adb: 'unknown', fastboot: 'unknown' };

/**
 * Dashboard device state.
 *
 * When running inside Electron it probes real devices over the secure IPC
 * bridge (window.mss.detectDevices → ADB/Fastboot). In a plain browser (tests /
 * `vite` preview) there is no bridge, so it resolves to "disconnected".
 */
export function useDeviceStatus(): UseDeviceStatus {
  const [state, setState] = useState<DetectionState>('idle');
  const [device, setDevice] = useState<DeviceSnapshot | null>(null);
  const [availability, setAvailability] = useState<ToolAvailability>(UNKNOWN_AVAILABILITY);

  const detect = useCallback(() => {
    setState('detecting');

    const bridge = typeof window !== 'undefined' ? window.mss : undefined;
    if (!bridge) {
      window.setTimeout(() => {
        setDevice(null);
        setState('disconnected');
      }, 600);
      return;
    }

    void bridge
      .detectDevices()
      .then((result) => {
        setAvailability({
          adb: result.adbAvailable ? 'yes' : 'no',
          fastboot: result.fastbootAvailable ? 'yes' : 'no',
        });
        const primary = pickPrimaryDevice(result);
        if (primary) {
          setDevice(toSnapshot(primary));
          setState('connected');
        } else {
          setDevice(null);
          setState('disconnected');
        }
      })
      .catch(() => {
        setDevice(null);
        setState('disconnected');
      });
  }, []);

  return { state, device, availability, detect };
}
