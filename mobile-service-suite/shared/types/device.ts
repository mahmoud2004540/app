/**
 * Serializable device-detection contract shared between the Electron main
 * process (producer) and the renderer (consumer) across the IPC boundary.
 */
export type DeviceTransport = 'adb' | 'fastboot';

/** ADB connection states as reported by `adb devices`. */
export type AdbState = 'device' | 'unauthorized' | 'offline' | 'no permissions' | 'recovery';

export type TriBool = 'yes' | 'no' | 'unknown';

export interface DetectedDevice {
  /** Serial / transport id reported by adb or fastboot. */
  id: string;
  transport: DeviceTransport;
  /** Raw connection state ('device', 'unauthorized', 'fastboot', …). */
  state: string;
  brand?: string;
  manufacturer?: string;
  model?: string;
  androidVersion?: string;
  sdk?: string;
  buildNumber?: string;
  serialNumber?: string;
  chipset?: string;
  cpuAbi?: string;
  batteryPercent?: number;
  totalRamKb?: number;
  bootloaderUnlocked?: TriBool;
  oemUnlockAllowed?: TriBool;
  /** FRP / factory-reset protection is DIAGNOSED only, never bypassed. */
  frpState?: TriBool;
}

export interface DetectionResult {
  adbAvailable: boolean;
  fastbootAvailable: boolean;
  devices: DetectedDevice[];
}
