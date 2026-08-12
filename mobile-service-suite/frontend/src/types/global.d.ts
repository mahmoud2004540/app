import type { MobileServiceSuiteApi } from '../../../electron/preload';

declare global {
  interface Window {
    /** Secure IPC bridge exposed by the Electron preload script. */
    mss: MobileServiceSuiteApi;
  }
}

export {};
