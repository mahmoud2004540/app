import { app, BrowserWindow, dialog, ipcMain, shell } from 'electron';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { DeviceDetectionService } from '../backend/services/detection/DeviceDetectionService';
import { AdbManagerService } from '../backend/services/adb/AdbManagerService';
import { FastbootManagerService } from '../backend/services/fastboot/FastbootManagerService';
import { DriverManagerService } from '../backend/services/drivers/DriverManagerService';
import { NodeCommandRunner } from '../backend/services/process/CommandRunner';
import { ToolManagerService } from '../backend/services/tools/ToolManagerService';
import { AppDatabase } from '../backend/database/Database';
import { ToolRepository } from '../backend/database/repositories/ToolRepository';
import { ok, err, type Result } from '../shared/types/result';

const asString = (value: unknown): string => (typeof value === 'string' ? value : '');

function launchExecutable(execPath: string): Result<string> {
  try {
    const child = spawn(execPath, [], { detached: true, stdio: 'ignore' });
    child.unref();
    return ok('launched');
  } catch (e) {
    return err(e instanceof Error ? e.message : String(e));
  }
}

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// In development Vite serves the renderer; in production we load the built files.
const isDev = !app.isPackaged;
const DEV_SERVER_URL = 'http://localhost:5173';

// Application metadata surfaced to the renderer over a locked-down IPC bridge.
const APP_INFO = {
  name: 'Mobile Service Suite',
  version: app.getVersion(),
  phase: 'PHASE 9 — Tool Manager',
} as const;

// Shared services. Both are safe to construct when the CLIs are absent.
const detectionService = new DeviceDetectionService();
const adbManager = new AdbManagerService();
const fastbootManager = new FastbootManagerService();
const driverManager = new DriverManagerService();

// Initialized on app-ready (needs the userData path).
let database: AppDatabase | null = null;
let toolStore: ToolRepository | null = null;
let toolManager: ToolManagerService | null = null;

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

function initDatabase(): void {
  database = AppDatabase.open(path.join(app.getPath('userData'), 'mss.sqlite'));
  toolStore = new ToolRepository(database.connection);
  toolManager = new ToolManagerService({
    runner: new NodeCommandRunner(),
    store: toolStore,
    fileExists: existsSync,
    launch: launchExecutable,
    log: database.logs,
  });
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

  // Fastboot Manager (PHASE 7). Unlock/lock/erase/flash are confirmed in the UI
  // and validated in the service. Bootloader lock state is changed only as an
  // explicit technician action; account protection is never bypassed.
  ipcMain.handle('fastboot:devices', () => fastbootManager.listDevices());
  ipcMain.handle('fastboot:getVar', (_e, s, name) =>
    fastbootManager.getVar(asString(s), asString(name)),
  );
  ipcMain.handle('fastboot:getAllVars', (_e, s) => fastbootManager.getAllVars(asString(s)));
  ipcMain.handle('fastboot:reboot', (_e, s, target) =>
    fastbootManager.reboot(asString(s), asString(target)),
  );
  ipcMain.handle('fastboot:unlock', (_e, s) => fastbootManager.unlock(asString(s)));
  ipcMain.handle('fastboot:lock', (_e, s) => fastbootManager.lock(asString(s)));
  ipcMain.handle('fastboot:erase', (_e, s, part) =>
    fastbootManager.erase(asString(s), asString(part)),
  );
  ipcMain.handle('fastboot:flash', (_e, s, part, img) =>
    fastbootManager.flash(asString(s), asString(part), asString(img)),
  );

  // Driver Manager (PHASE 8). Read-only status; the suite never installs drivers.
  ipcMain.handle('drivers:list', () => driverManager.list());
  ipcMain.handle('system:openDeviceManager', () => {
    if (process.platform !== 'win32') {
      return { ok: false as const, error: 'Device Manager is only available on Windows' };
    }
    spawn('cmd', ['/c', 'start', '', 'devmgmt.msc'], { detached: true, windowsHide: true });
    return { ok: true as const, value: 'opened' };
  });
  ipcMain.handle('system:openExternal', (_e, url) => {
    if (typeof url === 'string' && (url.startsWith('https://') || url.startsWith('http://'))) {
      void shell.openExternal(url);
      return { ok: true as const, value: url };
    }
    return { ok: false as const, error: 'Only http/https URLs may be opened' };
  });

  // Tool Manager (PHASE 9). Launches the technician's own installed tools; never
  // bundles or modifies commercial software.
  ipcMain.handle('tools:list', () => toolManager?.list() ?? { tools: [] });
  ipcMain.handle('tools:setPath', (_e, key, p) =>
    toolManager?.setPath(asString(key), asString(p)) ?? { ok: false, error: 'not ready' },
  );
  ipcMain.handle('tools:checkVersion', (_e, key) =>
    toolManager?.checkVersion(asString(key)) ?? { ok: false, error: 'not ready' },
  );
  ipcMain.handle('tools:launch', (_e, key) =>
    toolManager?.launch(asString(key)) ?? { ok: false, error: 'not ready' },
  );
  ipcMain.handle('tools:openFolder', (_e, key) => {
    const p = toolStore?.getPath(asString(key));
    if (!p) return { ok: false as const, error: 'Tool path is not set' };
    shell.showItemInFolder(p);
    return { ok: true as const, value: p };
  });

  // Native file dialogs used by file-oriented ADB/Fastboot actions.
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
  initDatabase();
  registerIpcHandlers();
  createMainWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createMainWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('will-quit', () => {
  database?.close();
  database = null;
});
