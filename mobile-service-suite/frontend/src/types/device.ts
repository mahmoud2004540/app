/**
 * Presentation view-model for a connected device, consumed by the Dashboard.
 *
 * It mirrors the core `Device` entity but is shaped for display (pre-formatted
 * strings). PHASE 5 maps real ADB/Fastboot probes into this shape.
 */
export type TriState = 'yes' | 'no' | 'unknown';

export interface DeviceSnapshot {
  brand: string;
  model: string;
  imei: string;
  serial: string;
  androidVersion: string;
  buildNumber: string;
  cpu: string;
  ram: string;
  storage: string;
  batteryPercent: number;
  usbMode: string;
  adbConnected: boolean;
  fastbootConnected: boolean;
  bootloaderUnlocked: TriState;
  oemUnlocked: TriState;
  frpLocked: TriState;
}

export type DetectionState = 'idle' | 'detecting' | 'connected' | 'disconnected';
