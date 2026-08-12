import type { TriBool } from './device';

export type DriverInstallStatus = 'installed' | 'not-installed' | 'unknown';

/** Presentation status for one driver, produced by the Driver Manager. */
export interface DriverStatus {
  key: string;
  name: string;
  vendor: string;
  supportedBrands: string[];
  description: string;
  /** Official vendor / Google download page. Never a third-party mirror. */
  downloadUrl: string;
  installed: TriBool;
  version: string | null;
  status: DriverInstallStatus;
  /** Whether this driver can be automatically checked on the current OS. */
  checkable: boolean;
}

export interface DriverReport {
  platform: string;
  drivers: DriverStatus[];
}
