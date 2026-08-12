import type { DetectedDevice, DetectionResult } from '@shared/types/device';
import type { DeviceSnapshot, TriState } from '../types/device';

const DASH = '—';

function formatKbAsGb(kb: number | undefined): string {
  if (kb === undefined || kb <= 0) return DASH;
  return `${(kb / 1024 / 1024).toFixed(1)} GB`;
}

/** Pick the most relevant device to feature on the dashboard. */
export function pickPrimaryDevice(result: DetectionResult): DetectedDevice | null {
  const ready = result.devices.find((d) => d.transport === 'adb' && d.state === 'device');
  return ready ?? result.devices[0] ?? null;
}

/** Map a raw detected device into the dashboard's presentation snapshot. */
export function toSnapshot(d: DetectedDevice): DeviceSnapshot {
  const tri = (v: DetectedDevice['bootloaderUnlocked']): TriState => v ?? 'unknown';
  return {
    brand: d.brand ?? d.manufacturer ?? 'Unknown',
    model: d.model ?? d.id,
    imei: DASH, // IMEI requires privileged access; surfaced via Device Info in a later phase.
    serial: d.serialNumber ?? d.id,
    androidVersion: d.androidVersion ?? DASH,
    buildNumber: d.buildNumber ?? DASH,
    cpu: d.chipset ?? d.cpuAbi ?? DASH,
    ram: formatKbAsGb(d.totalRamKb),
    storage: DASH,
    batteryPercent: d.batteryPercent ?? 0,
    usbMode: d.transport.toUpperCase(),
    adbConnected: d.transport === 'adb' && d.state === 'device',
    fastbootConnected: d.transport === 'fastboot',
    bootloaderUnlocked: tri(d.bootloaderUnlocked),
    oemUnlocked: tri(d.oemUnlockAllowed),
    frpLocked: tri(d.frpState),
  };
}
