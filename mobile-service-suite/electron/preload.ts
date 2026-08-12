import { contextBridge, ipcRenderer } from 'electron';
import type { DetectionResult } from '@shared/types/device';
import type { Result } from '@shared/types/result';

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

export interface FileFilter {
  name: string;
  extensions: string[];
}

const adb = {
  reboot: (serial: string, target: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:reboot', serial, target),
  connect: (hostPort: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:connect', hostPort),
  disconnect: (hostPort?: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:disconnect', hostPort),
  install: (serial: string, apkPath: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:install', serial, apkPath),
  uninstall: (serial: string, pkg: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:uninstall', serial, pkg),
  listPackages: (serial: string): Promise<Result<string[]>> =>
    ipcRenderer.invoke('adb:listPackages', serial),
  shell: (serial: string, command: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:shell', serial, command),
  pull: (serial: string, remotePath: string, localPath: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:pull', serial, remotePath, localPath),
  push: (serial: string, localPath: string, remotePath: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:push', serial, localPath, remotePath),
  logcat: (serial: string, lines?: number): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:logcat', serial, lines),
  screenshot: (serial: string, destPath: string): Promise<Result<string>> =>
    ipcRenderer.invoke('adb:screenshot', serial, destPath),
};

const fastboot = {
  devices: (): Promise<Result<string[]>> => ipcRenderer.invoke('fastboot:devices'),
  getVar: (serial: string, name: string): Promise<Result<string>> =>
    ipcRenderer.invoke('fastboot:getVar', serial, name),
  getAllVars: (serial: string): Promise<Result<Record<string, string>>> =>
    ipcRenderer.invoke('fastboot:getAllVars', serial),
  reboot: (serial: string, target: string): Promise<Result<string>> =>
    ipcRenderer.invoke('fastboot:reboot', serial, target),
  unlock: (serial: string): Promise<Result<string>> =>
    ipcRenderer.invoke('fastboot:unlock', serial),
  lock: (serial: string): Promise<Result<string>> => ipcRenderer.invoke('fastboot:lock', serial),
  erase: (serial: string, partition: string): Promise<Result<string>> =>
    ipcRenderer.invoke('fastboot:erase', serial, partition),
  flash: (serial: string, partition: string, imagePath: string): Promise<Result<string>> =>
    ipcRenderer.invoke('fastboot:flash', serial, partition, imagePath),
};

const dialogApi = {
  openFile: (filters?: FileFilter[]): Promise<string | null> =>
    ipcRenderer.invoke('dialog:openFile', filters),
  saveFile: (defaultName?: string): Promise<string | null> =>
    ipcRenderer.invoke('dialog:saveFile', defaultName),
};

const api = {
  /** Returns static application metadata from the main process. */
  getAppInfo: (): Promise<AppInfo> => ipcRenderer.invoke('app:getInfo'),
  /** Probe connected devices over ADB and Fastboot. */
  detectDevices: (): Promise<DetectionResult> => ipcRenderer.invoke('devices:detect'),
  /** ADB Manager operations (PHASE 6). */
  adb,
  /** Fastboot Manager operations (PHASE 7). */
  fastboot,
  /** Native file dialogs. */
  dialog: dialogApi,
};

export type MobileServiceSuiteApi = typeof api;

contextBridge.exposeInMainWorld('mss', api);
