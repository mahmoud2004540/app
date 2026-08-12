import type { SupportedBrand, SupportedPlatform } from '@shared/constants/app';

/** How the device is currently connected / which mode it is in. */
export type ConnectionMode = 'adb' | 'fastboot' | 'recovery' | 'download' | 'unknown';

/**
 * Core Device entity — the central domain object of the suite.
 *
 * PHASE 1 defines the shape only; population from real USB/ADB/Fastboot probes
 * is implemented in PHASE 5 onward. Fields are optional where the information is
 * not always available for every connection mode.
 */
export interface Device {
  readonly id: string;
  brand?: SupportedBrand | string;
  model?: string;
  manufacturer?: string;
  imei?: string;
  serialNumber?: string;
  androidVersion?: string;
  buildNumber?: string;
  chipset?: SupportedPlatform | string;
  cpu?: string;
  ramBytes?: number;
  storageBytes?: number;
  batteryPercent?: number;
  connectionMode: ConnectionMode;
  adbConnected: boolean;
  fastbootConnected: boolean;
  bootloaderUnlocked?: boolean;
  oemUnlocked?: boolean;
  /** FRP / protection is diagnosed and reported only — never bypassed. */
  frpLocked?: boolean;
  detectedAt: string;
}
