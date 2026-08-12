import { contextBridge, ipcRenderer } from 'electron';

/**
 * Secure bridge between the isolated renderer and the main process.
 *
 * Only an explicit, typed allow-list of channels is exposed. The renderer never
 * receives the raw `ipcRenderer` object, and node integration stays disabled.
 * See docs/SECURITY.md.
 */
export interface AppInfo {
  name: string;
  version: string;
  phase: string;
}

const api = {
  /** Returns static application metadata from the main process. */
  getAppInfo: (): Promise<AppInfo> => ipcRenderer.invoke('app:getInfo'),
};

export type MobileServiceSuiteApi = typeof api;

contextBridge.exposeInMainWorld('mss', api);
