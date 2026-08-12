import { useCallback, useState } from 'react';
import type { DetectionState, DeviceSnapshot } from '../types/device';

interface UseDeviceStatus {
  state: DetectionState;
  device: DeviceSnapshot | null;
  detect: () => void;
}

/**
 * Dashboard device state.
 *
 * PHASE 3 ships the UI against this hook with no real device attached: `detect()`
 * simulates a probe and resolves to "disconnected". PHASE 5 replaces the body
 * with a real call over the secure IPC bridge (window.mss) to ADB/Fastboot,
 * keeping the same return shape so the Dashboard needs no changes.
 */
export function useDeviceStatus(): UseDeviceStatus {
  const [state, setState] = useState<DetectionState>('idle');
  const [device, setDevice] = useState<DeviceSnapshot | null>(null);

  const detect = useCallback(() => {
    setState('detecting');
    // Simulated latency; no real device is probed in PHASE 3.
    window.setTimeout(() => {
      setDevice(null);
      setState('disconnected');
    }, 600);
  }, []);

  return { state, device, detect };
}
