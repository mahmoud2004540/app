import { app, BrowserWindow, ipcMain, shell } from 'electron';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// In development Vite serves the renderer; in production we load the built files.
const isDev = !app.isPackaged;
const DEV_SERVER_URL = 'http://localhost:5173';

// Application metadata surfaced to the renderer over a locked-down IPC bridge.
const APP_INFO = {
  name: 'Mobile Service Suite',
  version: app.getVersion(),
  phase: 'PHASE 1 — Project Setup',
} as const;

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
  // Minimal, read-only handler for PHASE 1. Real device/tool handlers arrive in later phases.
  ipcMain.handle('app:getInfo', () => APP_INFO);
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
