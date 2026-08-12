/** How a driver's installation is detected on the current OS. */
export type DriverDetect =
  | { type: 'adb' }
  | { type: 'fastboot' }
  | { type: 'pnputil'; match: string[] };

export interface DriverInfo {
  key: string;
  name: string;
  vendor: string;
  supportedBrands: string[];
  description: string;
  /** Official download page only (Google / vendor) — never a third-party mirror. */
  downloadUrl: string;
  detect: DriverDetect;
}

/**
 * Static catalog of drivers the suite knows about. New drivers can be added here
 * without touching the service or UI (data-driven, Modular Architecture).
 */
export const DRIVER_CATALOG: readonly DriverInfo[] = [
  {
    key: 'adb',
    name: 'Android ADB Interface',
    vendor: 'Google',
    supportedBrands: ['all'],
    description: 'USB debugging bridge used by ADB operations across all Android brands.',
    downloadUrl: 'https://developer.android.com/tools/releases/platform-tools',
    detect: { type: 'adb' },
  },
  {
    key: 'fastboot',
    name: 'Android Bootloader Interface',
    vendor: 'Google',
    supportedBrands: ['all'],
    description: 'Bootloader/fastboot-mode interface used by Fastboot operations.',
    downloadUrl: 'https://developer.android.com/tools/releases/platform-tools',
    detect: { type: 'fastboot' },
  },
  {
    key: 'usb-serial',
    name: 'Google USB Driver',
    vendor: 'Google',
    supportedBrands: ['all'],
    description: 'Generic Android USB driver for Windows (ADB/Fastboot over USB).',
    downloadUrl: 'https://developer.android.com/studio/run/win-usb',
    detect: { type: 'pnputil', match: ['Google, Inc.', 'WinUSB', 'Android'] },
  },
  {
    key: 'samsung',
    name: 'Samsung USB Driver',
    vendor: 'Samsung',
    supportedBrands: ['samsung'],
    description: 'Samsung Android USB driver for ADB, MTP and Download (Odin) mode.',
    downloadUrl: 'https://developer.samsung.com/android-usb-driver',
    detect: { type: 'pnputil', match: ['SAMSUNG', 'ssudbus', 'Samsung Electronics'] },
  },
  {
    key: 'qualcomm',
    name: 'Qualcomm HS-USB / QDLoader',
    vendor: 'Qualcomm',
    supportedBrands: ['qualcomm'],
    description: 'Qualcomm QDLoader HS-USB 9008 driver for EDL / emergency download mode.',
    downloadUrl: 'https://developer.android.com/studio/run/oem-usb',
    detect: { type: 'pnputil', match: ['Qualcomm', 'QDLoader', 'HS-USB'] },
  },
  {
    key: 'mediatek',
    name: 'MediaTek USB VCOM / Preloader',
    vendor: 'MediaTek',
    supportedBrands: ['mediatek'],
    description: 'MediaTek preloader / VCOM driver used by SP Flash Tool.',
    downloadUrl: 'https://developer.android.com/studio/run/oem-usb',
    detect: { type: 'pnputil', match: ['MediaTek', 'MTK', 'VCOM', 'Preloader'] },
  },
  {
    key: 'unisoc',
    name: 'Unisoc / SPRD USB Driver',
    vendor: 'Unisoc',
    supportedBrands: ['unisoc'],
    description: 'Unisoc (Spreadtrum) diagnostic / download driver used by ResearchDownload.',
    downloadUrl: 'https://developer.android.com/studio/run/oem-usb',
    detect: { type: 'pnputil', match: ['SPRD', 'Unisoc', 'Spreadtrum'] },
  },
];
