import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { DeviceDetectionService } from '../backend/services/detection/DeviceDetectionService';
import { AdbManagerService } from '../backend/services/adb/AdbManagerService';

const asString = (value: unknown): string => (typeof value === 'string' ? value : '');

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// In development Vite serves the renderer; in production we load the built files.
const isDev = !app.isPackaged;
const DEV_SERVER_URL = 'http://localhost:5173';

// Application metadata surfaced to the renderer over a locked-down IPC bridge.
const APP_INFO = {
  name: 'Mobile Service Suite',
  version: app.getVersion(),
  phase: 'PHASE 6 — ADB Manager',
} as const;

// Shared services. Both are safe to construct when the CLIs are absent.
const detectionService = new DeviceDetectionService();
const adbManager = new AdbManagerService();

function createMainWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 640,
    backgroundColor: '#0f1420',
    show: false,
    title: APP_INFO.name,
    webPreferences: {
      // Security hardening (see docs/SECURITY.md).
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
    },
  });

  window.once('ready-to-show', () => window.show());

  // Open external links in the user's browser, never inside the app window.
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://') || url.startsWith('http://')) {
      void shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  if (isDev) {
    void window.loadURL(DEV_SERVER_URL);
    window.webContents.openDevTools({ mode: 'detach' });
  } else {
    void window.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  return window;
}

function registerIpcHandlers(): void {
  ipcMain.handle('app:getInfo', () => APP_INFO);

  // Device detection (PHASE 5). Read-only probe; returns tool availability + devices.
  ipcMain.handle('devices:detect', () => detectionService.detect());

  // ADB Manager (PHASE 6). Sensitive actions are confirmed in the UI; inputs are
  // additionally validated inside the service.
  ipcMain.handle('adb:reboot', (_e, s, target) => adbManager.reboot(asString(s), asString(target)));
  ipcMain.handle('adb:connect', (_e, hp) => adbManager.connect(asString(hp)));
  ipcMain.handle('adb:disconnect', (_e, hp) =>
    adbManager.disconnect(typeof hp === 'string' && hp ? hp : undefined),
  );
  ipcMain.handle('adb:install', (_e, s, apk) => adbManager.install(asString(s), asString(apk)));
  ipcMain.handle('adb:uninstall', (_e, s, pkg) => adbManager.uninstall(asString(s), asString(pkg)));
  ipcMain.handle('adb:listPackages', (_e, s) => adbManager.listPackages(asString(s)));
  ipcMain.handle('adb:shell', (_e, s, cmd) => adbManager.shell(asString(s), asString(cmd)));
  ipcMain.handle('adb:pull', (_e, s, r, l) =>
    adbManager.pull(asString(s), asString(r), asString(l)),
  );
  ipcMain.handle('adb:push', (_e, s, l, r) => adbManager.push(asString(s), asString(l), asString(r)));
  ipcMain.handle('adb:logcat', (_e, s, lines) =>
    adbManager.logcat(asString(s), typeof lines === 'number' ? lines : 200),
  );
  ipcMain.handle('adb:screenshot', (_e, s, dest) =>
    adbManager.screenshot(asString(s), asString(dest)),
  );

  // Native file dialogs used by file-oriented ADB actions.
  ipcMain.handle('dialog:openFile', async (_e, filters) => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      ...(Array.isArray(filters) ? { filters } : {}),
    });
    return result.canceled ? null : (result.filePaths[0] ?? null);
  });
  ipcMain.handle('dialog:saveFile', async (_e, defaultName) => {
    const result = await dialog.showSaveDialog(
      typeof defaultName === 'string' ? { defaultPath: defaultName } : {},
    );
    return result.canceled ? null : (result.filePath ?? null);
  });
}

app.whenReady().then(() => {
  registerIpcHandlers();
  createMainWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
